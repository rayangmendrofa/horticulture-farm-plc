"""Web HMI: Modbus TCP client of the PLC + a small HTTP/JSON API and a single-page UI.

The HMI talks to the PLC only through the %MW interface (tags.py, FDS 9), so it works the
same against the soft-PLC, the fast-forward runner and the real OpenPLC runtime.

Time base: the PLC heartbeat (%MW40) counts scans of the 50 ms task, so the HMI derives
*process* time from it (heartbeat delta x 0.05 s). Trends are therefore correct in virtual
time when the demo runs fast-forward, and the HMI needs no knowledge of the speed.

The optional *field simulation* panel talks straight to the plant server (weather, time
of day, speed, fault injection, panel push-buttons). It is a demo tool, not part of the
operator HMI (PRD HR-11).
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import tags
from .modbus import ModbusClient, ModbusError
from .plant import BUTTONS, FAULTS
from .plant_server import (HR_BUTTONS, HR_CLOCK, HR_FAULTS, HR_SCENARIO, HR_SPEED, IR_TRUTH,
                           SPEEDS)
from .weather import SCENARIOS

WEB = Path(__file__).resolve().parent / "web"
SCAN_S = 0.05                 # PLC task interval: heartbeat +1 per scan
FAST_SPAN_S = 600             # 10 min trend of EC, pH, flow (PRD HR-08)
SLOW_SPAN_S = 24 * 3600       # 24 h trend of climate
FAST_EVERY_S, SLOW_EVERY_S = 1.0, 60.0
COMMS_TIMEOUT_S = 2.0         # heartbeat unchanged this long (wall time) = comms lost

# Field-simulation fault catalogue, grouped for the panel: (plant.FAULTS id, title)
FAULT_GROUPS = (
    ("Signals (wire break, < 3.6 mA)", (
        ("lt201_break", "LT-201 tank level"), ("ft201_break", "FT-201 flow"),
        ("pt201_break", "PT-201 pressure"), ("ec_break", "AIT-301 EC"),
        ("ph_a_break", "AIT-302 pH A"), ("ph_b_break", "AIT-303 pH B"),
        ("ft402_break", "FT-402 drain"), ("rt101_break", "RT-101 radiation"),
        ("st101_break", "ST-101 wind"), ("tt101_break", "TT-101 outside temp"),
        ("tt501_break", "TT-501 greenhouse temp"), ("mt501_break", "MT-501 greenhouse RH"),
        ("at502_break", "AT-502 CO2"), ("zt511_break", "ZT-511 vent position"),
        ("rain_wire_break", "Rain sensor wire"), ("clock_frozen", "I/O clock frozen"))),
    ("Equipment", (
        ("p201_trip", "P-201 trips"), ("p311_trip", "P-311 trips"), ("p312_trip", "P-312 trips"),
        ("p313_trip", "P-313 trips"), ("f601_trip", "F-601 trips"), ("f602_trip", "F-602 trips"),
        ("f603_trip", "F-603 trips"), ("p531_trip", "P-531 trips"), ("p541_trip", "P-541 trips"),
        ("vent_stuck", "Vent jammed"), ("m511_overload", "Vent motor overload"),
        ("net_stuck", "Shade net jammed"), ("m521_overload", "Net motor overload"))),
    ("Process", (
        ("ph_b_drift", "pH B probe drifts"), ("burst_pipe", "Burst pipe"),
        ("blocked_line", "Blocked main line"), ("z3_clogged", "Zone 3 drippers clogged"),
        ("z4_leak", "Zone 4 leak"), ("refill_fail", "Refill valve fails"),
        ("lsl201_dry", "T-201 runs dry"), ("stock_a_empty", "Stock A empty"),
        ("stock_b_empty", "Stock B empty"), ("acid_empty", "Acid tank empty"),
        ("pad_sump_low", "Pad sump low"), ("fog_inlet_low", "Fog inlet starved"))),
)
_listed = [f for _, fs in FAULT_GROUPS for f, _ in fs]
assert sorted(_listed + ["estop"]) == sorted(FAULTS), set(FAULTS) ^ set(_listed + ["estop"])

TRUTH_KEYS = ("t_in", "rh_in", "vent", "net", "ec", "ph", "flow", "press", "level", "co2",
              "watchdog", "day", "speed", "fast")
TRUTH_SCALE = {"t_in": 10, "rh_in": 10, "vent": 10, "net": 10, "ec": 100, "ph": 100,
               "press": 100, "level": 10}

FAST_KEYS = ("ec", "ph", "flow", "sp_ec", "sp_ph")
SLOW_KEYS = ("t_in", "t_out", "rh_in", "vent_pos", "rad", "clock")


class Trend:
    """Samples keyed on process time (seconds), pruned to ``span``."""

    def __init__(self, keys, span, every):
        self.keys, self.span, self.every = ("t",) + tuple(keys), span, every
        self.data = {k: deque() for k in self.keys}
        self._next = None

    def add(self, t: float, values: dict):
        if self._next is not None and t < self._next:
            return
        self._next = t + self.every
        for k in self.keys:
            self.data[k].append(t if k == "t" else values.get(k))
        while self.data["t"] and self.data["t"][0] < t - self.span:
            for k in self.keys:
                self.data[k].popleft()

    def clear(self):
        for d in self.data.values():
            d.clear()
        self._next = None

    def dump(self) -> dict:
        return {k: list(v) for k, v in self.data.items()}


class HMIBackend:
    def __init__(self, plc=("127.0.0.1", 5502), plant=("127.0.0.1", 5020), poll_s=0.25):
        self.plc = ModbusClient(*plc, timeout=0.5)
        self.plant = ModbusClient(*plant, timeout=0.5) if plant else None
        self.poll_s = poll_s
        self.state: dict = {"ok": False}
        self.fast = Trend(FAST_KEYS, FAST_SPAN_S, FAST_EVERY_S)
        self.slow = Trend(SLOW_KEYS, SLOW_SPAN_S, SLOW_EVERY_S)
        self.t_proc = 0.0                 # process seconds since the HMI started
        self._last_hb, self._hb_wall = None, 0.0
        self._rate = deque(maxlen=40)     # (wall, process) pairs for the achieved speed
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="hmi-poll").start()
        return self

    def stop(self):
        self._stop.set()

    # -- polling ------------------------------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            self.poll()
            self._stop.wait(self.poll_s)

    def _read_mw(self, mw: int, n: int) -> list[int]:
        return self.plc.read_holding_registers(tags.MW_BASE + mw, n)

    def poll(self):
        now = time.time()
        st: dict = {"ok": False, "time": now}
        try:
            plc = tags.decode_status(self._read_mw(tags.STATUS_START, len(tags.STATUS_FIELDS)))
            sp_raw = self._read_mw(10, 28)
            man = self._read_mw(tags.MW_MAN_IRR, 6)
            hb = plc["heartbeat"]
            if self._last_hb is None:
                self._last_hb, self._hb_wall = hb, now
            elif hb != self._last_hb:
                d = (hb - self._last_hb) % 65536
                if d * SCAN_S <= 900:          # a restarted PLC resets the counter: skip the jump
                    self.t_proc += d * SCAN_S
                self._last_hb, self._hb_wall = hb, now
            self._rate.append((now, self.t_proc))
            ok = now - self._hb_wall < COMMS_TIMEOUT_S
            setpoints = {name: sp_raw[mw - 10] / scale for name, mw, _d, scale, *_ in tags.SETPOINTS}
            st.update(
                ok=ok, plc=plc, setpoints=setpoints, t_proc=self.t_proc, speed=self._speed(),
                manual={"irr": [k for k, b in tags.MAN_IRR_BITS.items() if man[0] & b],
                        "dose": {"a": man[1] / 10, "b": man[2] / 10, "acid": man[3] / 10},
                        "clim": [k for k, b in tags.MAN_CLIM_BITS.items() if man[4] & b],
                        "vent": man[5] / 10})
            if ok and self.t_proc >= 5.0:      # skip the first seconds: filters still settling
                with self._lock:
                    self.fast.add(self.t_proc, {
                        "ec": plc["ec"], "ph": plc["ph"], "flow": plc["flow"],
                        "sp_ec": setpoints["SP_EC"], "sp_ph": setpoints["SP_PH"]})
                    self.slow.add(self.t_proc, {k: plc[k] for k in SLOW_KEYS})
            if not ok:
                st["error"] = "PLC heartbeat stopped"
        except (ConnectionError, ModbusError, OSError) as e:
            st["error"] = f"PLC: {e}"
        st["sim"] = self._poll_plant()
        self.state = st

    def _speed(self):
        """Achieved process seconds per wall second over the last ~10 s."""
        if len(self._rate) < 2:
            return None
        (w0, p0), (w1, p1) = self._rate[0], self._rate[-1]
        return round((p1 - p0) / (w1 - w0), 1) if w1 - w0 > 1.0 else None

    def _poll_plant(self):
        if self.plant is None:
            return {"available": False}
        try:
            hr = self.plant.read_holding_registers(HR_FAULTS, 5)
            truth = self.plant.read_input_registers(IR_TRUTH, len(TRUTH_KEYS))
        except (ConnectionError, ModbusError, OSError):
            return {"available": False}
        bits = hr[0] | hr[1] << 16 | hr[2] << 32
        tr = {k: v / TRUTH_SCALE.get(k, 1) for k, v in zip(TRUTH_KEYS, truth)}
        tr["watchdog"], tr["fast"] = bool(tr["watchdog"]), bool(tr["fast"])
        return {"available": True, "faults": [f for i, f in enumerate(FAULTS) if bits >> i & 1],
                "scenario": SCENARIOS[hr[4]] if hr[4] < len(SCENARIOS) else "?", "truth": tr}

    def snapshot(self) -> dict:
        with self._lock:
            trends = {"fast": self.fast.dump(), "slow": self.slow.dump()}
        return {**self.state, "trends": trends}

    # -- commands to the PLC ---------------------------------------------------------------
    def command(self, cmd: str):
        self.plc.write_register(tags.MW_BASE + tags.MW_CMD, tags.CMD_BITS[cmd])

    def set_setpoints(self, values: dict):
        """Engineering units in, raw words out. The PLC clamps and writes back (FR-13);
        the HMI shows the read-back value as the value in force."""
        for name, v in values.items():
            mw, _default, scale = tags.SP[name]
            raw = round(float(v) * scale)
            if not 0 <= raw <= 65535:
                raise ValueError(f"{name}: {v} out of the register range")
            self.plc.write_register(tags.MW_BASE + mw, raw)

    def set_manual(self, irr=None, dose=None, clim=None, vent=None):
        if irr is not None:
            self.plc.write_register(tags.MW_BASE + tags.MW_MAN_IRR, _bits(irr, tags.MAN_IRR_BITS))
        if dose is not None:
            for key, mw in (("a", tags.MW_MAN_DOSE_A), ("b", tags.MW_MAN_DOSE_B),
                            ("acid", tags.MW_MAN_DOSE_ACID)):
                if key in dose:
                    self.plc.write_register(tags.MW_BASE + mw, _pct(dose[key]))
        if clim is not None:
            self.plc.write_register(tags.MW_BASE + tags.MW_MAN_CLIM, _bits(clim, tags.MAN_CLIM_BITS))
        if vent is not None:
            self.plc.write_register(tags.MW_BASE + tags.MW_MAN_VENT, _pct(vent))

    # -- field simulation (plant server) --------------------------------------------------
    def sim(self, body: dict):
        if self.plant is None:
            raise ConnectionError("no plant simulator configured")
        if "button" in body:
            self.plant.write_register(HR_BUTTONS, 1 << BUTTONS.index(body["button"]))
        if "fault" in body:
            words = self.plant.read_holding_registers(HR_FAULTS, 3)
            bits = words[0] | words[1] << 16 | words[2] << 32
            bit = 1 << FAULTS.index(body["fault"])
            bits = bits | bit if body.get("active") else bits & ~bit
            self.plant.write_registers(HR_FAULTS, [bits & 0xFFFF, bits >> 16 & 0xFFFF, bits >> 32 & 0xFFFF])
        if body.get("clear_faults"):
            self.plant.write_registers(HR_FAULTS, [0, 0, 0])
        if "scenario" in body:
            self.plant.write_register(HR_SCENARIO, SCENARIOS.index(body["scenario"]))
        if "clock" in body:
            h, _, m = str(body["clock"]).partition(":")
            minute = int(h) * 60 + int(m or 0)
            if not 0 <= minute < 1440:
                raise ValueError("clock must be 00:00-23:59")
            self.plant.write_register(HR_CLOCK, minute + 1)
            with self._lock:                  # a time jump makes the 24 h trend meaningless
                self.slow.clear()
        if "speed" in body:
            speed = int(body["speed"])
            if speed not in SPEEDS:
                raise ValueError(f"speed must be one of {SPEEDS}")
            self.plant.write_register(HR_SPEED, speed)


def _bits(names, table) -> int:
    word = 0
    for n in names:
        word |= table[n]
    return word


def _pct(v) -> int:
    return round(max(0.0, min(100.0, float(v))) * 10)


def make_handler(backend: HMIBackend):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            path = urlsplit(self.path).path              # ignore ?query (e.g. ?capture)
            if path in ("/", "/index.html"):
                self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._json(backend.snapshot())
            elif path == "/api/meta":
                self._json(meta())
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/api/cmd":
                    backend.command(body["cmd"])
                elif self.path == "/api/setpoints":
                    backend.set_setpoints(body["values"])
                elif self.path == "/api/manual":
                    backend.set_manual(body.get("irr"), body.get("dose"), body.get("clim"), body.get("vent"))
                elif self.path == "/api/sim":
                    backend.sim(body)
                else:
                    return self._send(404, b"not found", "text/plain")
                self._json({"ok": True})
            except (KeyError, ValueError, TypeError) as e:
                self._json({"ok": False, "error": f"bad request: {e}"}, 400)
            except (ConnectionError, ModbusError, OSError) as e:
                self._json({"ok": False, "error": str(e)}, 502)
    return Handler


def meta() -> dict:
    """Static tables for the page, from the single source of truth."""
    return {
        "setpoints": [{"name": n, "mw": mw, "default": d / s, "scale": s, "unit": u,
                       "lo": lo / s, "hi": hi / s} for n, mw, d, s, u, lo, hi in tags.SETPOINTS],
        "di": [{"addr": tags.di_addr(i), "tag": t} for i, t in enumerate(tags.DI_TAGS)],
        "do": [{"addr": tags.do_addr(i), "tag": t} for i, t in enumerate(tags.DO_TAGS)],
        "faults": [{"group": g, "faults": [{"id": f, "title": t} for f, t in fs]} for g, fs in FAULT_GROUPS],
        "scenarios": list(SCENARIOS), "speeds": list(SPEEDS),
        "man_irr": list(tags.MAN_IRR_BITS), "man_clim": list(tags.MAN_CLIM_BITS),
    }


class HMIServer:
    def __init__(self, backend: HMIBackend, host="127.0.0.1", port=8080):
        self.backend = backend
        self.httpd = ThreadingHTTPServer((host, port), make_handler(backend))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def start(self):
        self.backend.start()
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="hmi-http").start()
        return self

    def stop(self):
        self.backend.stop()
        self.httpd.shutdown()
        self.httpd.server_close()


def hostport(s, default_port):
    if not s or s.lower() == "none":
        return None
    host, _, port = s.rpartition(":") if ":" in s else (s, "", "")
    return host or "127.0.0.1", int(port or default_port)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="GH-1 web HMI")
    ap.add_argument("--plc", default="127.0.0.1:5502", help="PLC Modbus server (OpenPLC: <ip>:502)")
    ap.add_argument("--plant", default="127.0.0.1:5020", help="plant simulator, or 'none'")
    ap.add_argument("--http", default="127.0.0.1:8080")
    args = ap.parse_args(argv)
    hh, hp = hostport(args.http, 8080)
    srv = HMIServer(HMIBackend(hostport(args.plc, 502), hostport(args.plant, 5020)), hh, hp).start()
    print(f"hmi: http://{hh}:{srv.port}  (PLC {args.plc})  Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()
