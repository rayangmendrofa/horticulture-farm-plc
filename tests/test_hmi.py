"""Web HMI tests (HMI): the HTTP/JSON API against the fast-forward soft-PLC over real Modbus TCP.

The PLC is stepped by hand (``FastPLC.cycle``) and the HMI polled by hand, so every test
is deterministic. One cycle = ``speed`` scans of 50 ms.
"""
import json
import threading
import urllib.error
import urllib.request

import pytest

from farmsim import hmi
from farmsim.hmi import HMIBackend, HMIServer
from farmsim.plant import FAULTS, Plant
from farmsim.plant_server import PlantServer
from farmsim.softplc import FastPLC


class Rig:
    def __init__(self, clock="10:30"):
        self.ps = PlantServer("127.0.0.1", 0, Plant(clock=clock), passive=True).start()
        self.plc = FastPLC(self.ps, listen=("127.0.0.1", 0), speed=20)
        self.plc._to_image(all_areas=True)
        self.plc.server.start()
        self.backend = HMIBackend(("127.0.0.1", self.plc.port), ("127.0.0.1", self.ps.port))
        self.http = HMIServer(self.backend, "127.0.0.1", 0)
        threading.Thread(target=self.http.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.http.port}"

    def run(self, seconds: float):
        """Advance process time; the HMI polls once per PLC cycle (1 s at speed 20)."""
        for _ in range(max(1, round(seconds / (self.plc.speed * 0.05)))):
            self.plc.cycle()
            self.backend.poll()

    def get(self, path="/api/state"):
        with urllib.request.urlopen(self.url + path, timeout=5) as r:
            body = r.read()
            return json.loads(body) if path.startswith("/api") else body.decode()

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}") if e.code != 404 else {}

    def close(self):
        self.http.httpd.shutdown()
        self.http.httpd.server_close()
        self.plc.server.stop()
        self.ps.stop()
        self.backend.plc.close()
        self.backend.plant.close()


@pytest.fixture
def rig():
    r = Rig()
    r.run(2)
    yield r
    r.close()


@pytest.fixture
def night():
    """05:00, outside the day window: irrigation stays IDLE."""
    r = Rig("05:00")
    r.run(2)
    yield r
    r.close()


def test_hmi01_page_meta_and_state(rig):
    """HR-01..04: the page and its tables are served; the state decodes in engineering units."""
    assert "GH-1 Tropical Greenhouse" in rig.get("/")
    assert "GH-1 Tropical Greenhouse" in rig.get("/?capture")
    meta = rig.get("/api/meta")
    assert len(meta["setpoints"]) == 27 and len(meta["di"]) == 25 and len(meta["do"]) == 22
    listed = {f["id"] for g in meta["faults"] for f in g["faults"]}
    assert listed | {"estop"} == set(FAULTS)
    s = rig.get()
    assert s["ok"] and s["plc"]["clock_text"] in ("10:30", "10:31")
    assert s["setpoints"]["SP_EC"] == 2.5 and s["setpoints"]["SP_VENT_T"] == 28.0
    assert {d["tag"] for d in s["plc"]["devices"]} >= {"P-201", "M-511", "F-603"}
    assert s["sim"]["available"] and s["sim"]["truth"]["fast"] and s["sim"]["truth"]["speed"] == 20


def test_hmi02_commands_reach_the_plc(night):
    """HR-05: STOP in IDLE disables the program, START enables it, mode commands switch."""
    rig = night
    s = rig.get()["plc"]
    assert s["irr_step"] == 0 and s["irr_flags"]["enabled"] and not s["irr_flags"]["in_window"]
    assert rig.post("/api/cmd", {"cmd": "stop"})[0] == 200
    rig.run(1)
    assert not rig.get()["plc"]["irr_flags"]["enabled"]
    rig.post("/api/cmd", {"cmd": "start"})
    rig.run(1)
    assert rig.get()["plc"]["irr_flags"]["enabled"]
    rig.post("/api/cmd", {"cmd": "clim_manual"})
    rig.run(1)
    s = rig.get()["plc"]
    assert s["clim_flags"]["manual"] and s["clim_state_name"] == "MANUAL"
    assert rig.post("/api/cmd", {"cmd": "explode"})[0] == 400


def test_hmi03_setpoint_download_and_read_back(rig):
    """HR-06: download, PLC clamp, read-back of the value in force."""
    assert rig.post("/api/setpoints", {"values": {"SP_EC": 2.8, "SP_DAY_START": 360}})[0] == 200
    rig.run(1)
    sp = rig.get()["setpoints"]
    assert sp["SP_EC"] == 2.8 and sp["SP_DAY_START"] == 360
    rig.post("/api/setpoints", {"values": {"SP_EC": 9.0, "SP_COOL_T": 25.0}})
    rig.run(1)
    sp = rig.get()["setpoints"]
    assert sp["SP_EC"] == 4.0, "clamped to the upper limit"
    assert sp["SP_COOL_T"] == 29.0, "clamped to SP_VENT_T + 1.0"
    assert rig.post("/api/setpoints", {"values": {"SP_NOPE": 1}})[0] == 400


def test_hmi04_manual_outputs(night):
    """Manual words are written and read back; interlocks still apply in MANUAL."""
    rig = night
    rig.post("/api/manual", {"clim": ["F601"]})
    rig.run(3)
    s = rig.get()
    assert s["manual"]["clim"] == [] and not s["plc"]["devices"][12]["cmd"],         "AUTO: the PLC clears the manual words, so no stale request survives a mode change"
    rig.post("/api/cmd", {"cmd": "clim_manual"})
    rig.run(2)
    rig.post("/api/manual", {"clim": ["F601"], "vent": 0})    # night: the vent is open for humidity
    rig.run(3)
    dev = {d["key"]: d for d in rig.get()["plc"]["devices"]}
    assert dev["f601"]["blocked"] and dev["f601"]["interlocks"] == ["Vents not closed"]
    rig.run(60)
    s = rig.get()
    dev = {d["key"]: d for d in s["plc"]["devices"]}
    assert s["manual"]["clim"] == ["F601"] and dev["f601"]["running"] and dev["f601"]["manual"]
    rig.post("/api/manual", {"vent": 40})
    rig.run(10)
    s = rig.get()
    dev = {d["key"]: d for d in s["plc"]["devices"]}
    assert s["plc"]["vent_pos"] < 1.0 and "Fan commanded (pad-and-fan)" in dev["m511"]["interlocks"]
    rig.post("/api/manual", {"clim": []})
    rig.run(20)
    assert rig.get()["plc"]["vent_pos"] > 5.0


def test_hmi05_alarm_list_and_reset(rig):
    """HR-07: an injected fault gives a latched alarm; RESET clears it once the cause is gone."""
    rig.post("/api/sim", {"fault": "at502_break", "active": True})
    rig.run(12)
    al = {a["tag"]: a for a in rig.get()["plc"]["alarm_list"]}
    assert al["A34"]["active"] and al["A34"]["class"] == "warning"
    assert "at502_break" in rig.get()["sim"]["faults"]
    rig.post("/api/sim", {"clear_faults": True})
    rig.run(3)
    al = {a["tag"]: a for a in rig.get()["plc"]["alarm_list"]}
    assert not al["A34"]["active"] and al["A34"]["latched"]
    rig.post("/api/cmd", {"cmd": "reset"})
    rig.run(1)
    assert rig.get()["plc"]["alarm_list"] == []


def test_hmi06_trends_on_process_time(rig):
    """HR-08: trends are sampled on PLC scan time, so they are right in fast-forward."""
    rig.run(60)
    s = rig.get()
    fast, slow = s["trends"]["fast"], s["trends"]["slow"]
    assert 55 <= s["t_proc"] <= 70
    assert len(fast["t"]) >= 50 and fast["t"][-1] - fast["t"][0] >= 50
    assert all(abs(b - a - 1.0) < 1e-6 for a, b in zip(fast["t"], fast["t"][1:]))
    assert len(slow["t"]) >= 1 and slow["clock"][0] in (630, 631)


def test_hmi07_comms_watchdog(rig, monkeypatch):
    """HR-09: comms are lost when the heartbeat stops for 2 s, even if Modbus still answers."""
    assert rig.get()["ok"]
    wall = [hmi.time.time() + 3.0]
    monkeypatch.setattr(hmi.time, "time", lambda: wall[0])
    rig.backend.poll()                              # no PLC cycle: heartbeat unchanged
    s = rig.get()
    assert not s["ok"] and "heartbeat" in s["error"]
    rig.plc.cycle()
    rig.backend.poll()
    assert rig.get()["ok"]


def test_hmi08_field_simulation_panel(rig):
    """HR-11: weather scenario, time of day, speed and faults go to the plant server."""
    rig.post("/api/sim", {"fault": "z4_leak", "active": True})      # bit 24: second fault word
    rig.post("/api/sim", {"fault": "estop", "active": True})
    rig.run(2)                                  # the plant takes them after the next cycle's scans
    assert rig.ps.plant.faults == {"z4_leak", "estop"}
    assert rig.get()["plc"]["alarm_list"][0]["tag"] == "A00"
    rig.post("/api/sim", {"fault": "estop", "active": False})
    rig.post("/api/sim", {"scenario": "rain", "clock": "05:00", "speed": 40})
    rig.run(2)
    rig.run(3)
    s = rig.get()
    assert s["sim"]["scenario"] == "rain" and s["plc"]["clock_text"].startswith("05:0")
    assert rig.plc.speed == 40 and s["sim"]["truth"]["speed"] == 40
    assert s["trends"]["slow"]["t"] == [] or s["trends"]["slow"]["clock"][0] >= 300
    assert rig.post("/api/sim", {"speed": 7})[0] == 400
    assert rig.post("/api/sim", {"clock": "25:00"})[0] == 400
    rig.post("/api/sim", {"button": "reset"})
    rig.run(1)
    assert not rig.get()["sim"]["truth"]["watchdog"]
