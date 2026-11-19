"""FAT part B: run the GH-1 program on OpenPLC Runtime v4 against the virtual plant (OPL-02..08).

Run it where the runtime can reach the plant. With the runtime in Docker on WSL2:

    wsl -d Ubuntu -u root -- python3 tools/fat_openplc.py --plant-port 5021 --json result.json

The script starts the plant simulator itself (real time, 0.0.0.0:<plant-port>), so the
project must point PLANT at that port (tools/make_openplc_project.py --plant-port 5021).
It drives the PLC only through its Modbus server, exactly as the HMI does: commands and
setpoints into %MW, status from %MW40..139 (holding registers 1024 + n). Faults and panel
buttons are injected into the plant. Timings come from polling the runtime every 20 ms,
so they include the runtime's 50 ms remote-I/O cycle.

The runtime runs in real time (1x), so the irrigation test uses 10 L shots to keep the
whole run near 10 minutes. Exit code 0 = every test passed.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from farmsim import tags  # noqa: E402
from farmsim.modbus import ModbusClient  # noqa: E402
from farmsim.plant import BUTTONS, FAULTS, Plant  # noqa: E402
from farmsim.plant_server import HR_BUTTONS, HR_FAULTS, N_COILS, N_HR, PlantServer  # noqa: E402

FIELD_DO = [i for i, t in enumerate(tags.DO_TAGS) if not t.startswith("LAMP")]
POLL = 0.02


class Rig:
    def __init__(self, plc, plant_port, clock):
        self.plant = Plant(clock=clock, scenario="clear")
        self.plant_port = plant_port
        self.ps = PlantServer("0.0.0.0", plant_port, self.plant).start()
        self.plc = ModbusClient(*plc, timeout=1.0)
        self.t0 = time.monotonic()

    # -- PLC side (what the HMI does) ------------------------------------------------
    def status(self) -> dict:
        regs = self.plc.read_holding_registers(tags.MW_BASE + tags.STATUS_START, len(tags.STATUS_FIELDS))
        return tags.decode_status(regs)

    def cmd(self, name):
        self.plc.write_register(tags.MW_BASE + tags.MW_CMD, tags.CMD_BITS[name])

    def sp_write(self, name, raw):
        self.plc.write_register(tags.MW_BASE + tags.SP[name][0], raw)

    def sp_read(self, name) -> int:
        return self.plc.read_holding_registers(tags.MW_BASE + tags.SP[name][0], 1)[0]

    def manual_clim(self, bits=0, vent=None):
        self.plc.write_register(tags.MW_BASE + tags.MW_MAN_CLIM, bits)
        if vent is not None:
            self.plc.write_register(tags.MW_BASE + tags.MW_MAN_VENT, round(vent * 10))

    # -- plant side (the field) ------------------------------------------------------------
    def fault(self, name, on=True):
        img = self.ps.image
        with img.lock:
            bits = img.hr[HR_FAULTS] | img.hr[HR_FAULTS + 1] << 16 | img.hr[HR_FAULTS + 2] << 32
            bit = 1 << FAULTS.index(name)
            bits = bits | bit if on else bits & ~bit
            img.hr[HR_FAULTS:HR_FAULTS + 3] = [bits & 0xFFFF, bits >> 16 & 0xFFFF, bits >> 32 & 0xFFFF]

    def button(self, name):
        with self.ps.image.lock:
            self.ps.image.hr[HR_BUTTONS] = 1 << BUTTONS.index(name)

    def field_outputs(self):
        """What the plant actually receives from the runtime."""
        with self.ps.image.lock:
            return list(self.ps.image.coils[:N_COILS]), list(self.ps.image.hr[:N_HR])

    def plant_down(self):
        self.ps.stop()

    def plant_up(self):
        self.ps = PlantServer("0.0.0.0", self.plant_port, self.plant).start()

    # -- helpers -----------------------------------------------------------------------
    def wait(self, pred, timeout, what):
        t = time.monotonic()
        while time.monotonic() - t < timeout:
            s = self.status()
            if pred(s):
                return time.monotonic() - t, s
            time.sleep(POLL)
        s = self.status()
        raise AssertionError(f"{what} not reached in {timeout:.0f} s (step {s['irr_step_name']}, "
                             f"alarms {[a['tag'] for a in s['alarm_list']]})")

    def to_idle(self):
        """Bring irrigation to IDLE, AUTO, program disabled (no automatic starts), no alarms."""
        self.cmd("clim_auto")
        time.sleep(0.2)
        self.cmd("irr_auto")
        for _ in range(40):
            s = self.status()
            step = s["irr_step"]
            if step == 0 and not s["alarm_list"] and not s["irr_flags"]["enabled"]:
                return s
            if step == 0 and s["irr_flags"]["enabled"]:
                self.cmd("stop")
            elif step in (10, 20, 25):
                self.cmd("stop")
            elif step == 80:
                self.cmd("abort")
            elif step == 99 or s["alarm_list"]:
                self.cmd("reset")
            time.sleep(0.5)
        raise AssertionError(f"could not reach a clean IDLE: {self.status()['alarm_list']}")

    def start_shot(self):
        self.cmd("irrigate_now")
        self.wait(lambda s: s["irr_step"] == 20 and s["zone_vol"] > 2.0, 120, "SHOT")


# ======================================================================================
def opl02_comms(r: Rig) -> str:
    s = r.to_idle()
    hb0, t0 = s["heartbeat"], time.monotonic()
    time.sleep(2.0)
    s = r.status()
    rate = ((s["heartbeat"] - hb0) % 65536) / (time.monotonic() - t0)
    assert 18.0 <= rate <= 22.0, f"heartbeat {rate:.1f} per s, expected 20 (50 ms task)"
    assert abs(s["clock"] - r.plant.clock_min) <= 1, f"clock {s['clock']} vs plant {r.plant.clock_min}"
    assert r.sp_read("SP_EC") == 250 and r.sp_read("SP_RAIN_POS") == 100
    top = r.plc.read_holding_registers(tags.MW_BASE + 139, 1)          # %MW139 must be backed
    time.sleep(3.0)
    assert not r.ps.watchdog_tripped, "plant coupler watchdog tripped: coils not written every cycle"
    return (f"IDLE, no alarms after RESET; heartbeat {rate:.1f}/s; clock {s['clock_text']} = plant; "
            f"%MW139 readable ({top[0]}); coupler watchdog quiet")


def opl03_cycle(r: Rig) -> str:
    r.to_idle()
    for z in range(1, 5):
        r.sp_write(f"SP_SHOT_Z{z}", 10)
    s0 = r.status()
    sp_ec, sp_ph = r.sp_read("SP_EC") / 100, r.sp_read("SP_PH") / 100
    band_ec, band_ph = r.sp_read("SP_EC_BAND") / 100, r.sp_read("SP_PH_BAND") / 100
    r.cmd("irrigate_now")
    t0, steps, zones, worst, premix = time.monotonic(), [], set(), [0.0, 0.0], None
    while time.monotonic() - t0 < 400:
        s = r.status()
        if not steps or steps[-1] != s["irr_step"]:
            steps.append(s["irr_step"])
            if s["irr_step"] == 20 and premix is None:
                premix = time.monotonic() - t0
        if s["irr_step"] == 20 and s["zone"]:
            zones.add(s["zone"])
            if s["step_time"] >= 15:                     # after the mixer and sensor dead time
                worst = [max(worst[0], abs(s["ec"] - sp_ec)), max(worst[1], abs(s["ph"] - sp_ph))]
        if len(steps) > 1 and s["irr_step"] == 0:
            break
        assert s["irr_step"] != 99, f"trip: {[a['tag'] for a in s['alarm_list']]}"
        time.sleep(0.1)
    dur = time.monotonic() - t0
    s = r.status()
    for z in range(1, 5):
        r.sp_write(f"SP_SHOT_Z{z}", 60)
    water = s["water_day"] - s0["water_day"]
    assert steps[0] == 0 and 10 in steps and 20 in steps and 40 in steps and steps[-1] == 0, steps
    assert zones == {1, 2, 3, 4}, zones
    assert s["cycles_day"] == s0["cycles_day"] + 1 and not s["alarm_list"]
    assert worst[0] <= band_ec and worst[1] <= band_ph, worst
    assert 36 <= water <= 50, f"water {water} L for 4 x 10 L (changeover overlap is not counted, so it errs high)"
    return (f"steps {'→'.join(map(str, steps))}, zones 1-4, {dur:.0f} s, in band after {premix:.0f} s; "
            f"while watering |EC-SP| ≤ {worst[0]:.2f}, |pH-SP| ≤ {worst[1]:.2f}; {water} L; no alarms")


def opl04_estop(r: Rig) -> str:
    r.to_idle()
    r.start_shot()
    r.fault("estop")
    t0 = time.monotonic()
    while time.monotonic() - t0 < 2.0:
        coils, refs = r.field_outputs()
        if not any(coils[i] for i in FIELD_DO) and not any(refs):
            break
        time.sleep(0.005)
    t_off = time.monotonic() - t0
    assert t_off < 0.5, f"outputs still on after {t_off:.2f} s"
    s = r.status()
    assert s["irr_step"] == 99 and any(a["tag"] == "A00" for a in s["alarm_list"])
    r.cmd("reset")
    time.sleep(1.0)
    s = r.status()
    assert s["irr_step"] == 99 and any(a["tag"] == "A00" for a in s["alarm_list"]), "reset while pressed"
    r.fault("estop", False)
    time.sleep(3.0)
    s = r.status()
    assert s["irr_step"] == 99, "no automatic restart after release"
    r.cmd("reset")
    _, s = r.wait(lambda s: s["irr_step"] == 0 and not s["alarm_list"], 5, "IDLE after RESET")
    return (f"field outputs off {1000 * t_off:.0f} ms after the E-stop opened; step 99, A00; "
            f"RESET refused while pressed; no restart 3 s after release; RESET → IDLE, no alarms")


def opl05_analyser(r: Rig) -> str:
    r.to_idle()
    r.start_shot()
    r.fault("ec_break")
    t, s = r.wait(lambda s: s["irr_step"] == 99 and any(a["tag"] == "A23" for a in s["alarm_list"]),
                  3, "A23 trip")
    coils, refs = r.field_outputs()
    p311 = tags.DO_TAGS.index("P311")
    assert not coils[p311] and refs[0] == 0, "P-311 still dosing"
    assert "EC signal fault or A07" in s["interlocks"]["dose_ab"]
    r.fault("ec_break", False)
    time.sleep(1.0)
    r.cmd("reset")
    r.wait(lambda s: s["irr_step"] == 0 and not s["alarm_list"], 5, "IDLE after RESET")
    return (f"AIT-301 broken during SHOT → A23 and step 99 after {t:.2f} s; P-311 off, "
            f"dosing interlock names the EC fault; RESET after repair → IDLE")


def opl06_positioner(r: Rig) -> str:
    r.to_idle()
    r.cmd("clim_manual")
    time.sleep(0.5)
    r.manual_clim(0, 37.0)

    def settled(s):
        d = next(d for d in s["devices"] if d["key"] == "m511")
        return not (d["opening"] or d["closing"]) and abs(s["vent_pos"] - 37.0) < 3.0
    t1, s = r.wait(settled, 150, "vent at 37 %")
    time.sleep(3.0)
    pos = r.plant.vent_pos
    err = abs(pos - 37.0)
    assert err <= 2.0, f"vent {pos:.1f} %"
    r.manual_clim(0, 0.0)
    t2, s = r.wait(lambda s: s["inputs"]["ZSC511"], 150, "vent closed limit")
    r.manual_clim(0, 0.0)
    r.cmd("clim_auto")
    time.sleep(0.5)
    assert r.status()["clim_state"] == 10
    return (f"MANUAL 37 % → settled in {t1:.0f} s at {pos:.1f} % (plant), error {err:.1f} % "
            f"(3-point step over the 50 ms remote I/O); 0 % → closed limit in {t2:.0f} s; AUTO → VENT")


def opl07_setpoints(r: Rig) -> str:
    r.to_idle()
    r.sp_write("SP_EC", 900)
    r.sp_write("SP_COOL_T", 250)
    time.sleep(0.5)
    ec, cool, vent = r.sp_read("SP_EC"), r.sp_read("SP_COOL_T"), r.sp_read("SP_VENT_T")
    r.sp_write("SP_EC", 250)
    r.sp_write("SP_COOL_T", 320)
    time.sleep(0.5)
    assert ec == 400 and cool == vent + 10, (ec, cool, vent)
    assert r.sp_read("SP_EC") == 250 and r.sp_read("SP_COOL_T") == 320
    return f"SP_EC 9.00 → clamped to {ec / 100:.2f}; SP_COOL_T 25.0 → {cool / 10:.1f} (= SP_VENT_T + 1.0); defaults restored"


def opl08_plant_loss(r: Rig) -> str:
    r.to_idle()
    r.start_shot()
    r.plant_down()
    t, s = r.wait(lambda s: s["irr_step"] == 99 and any(a["tag"] == "A00" for a in s["alarm_list"]),
                  3, "trip on plant loss")
    out = [n for n in tags.DO_TAGS if s["outputs"][n] and not n.startswith("LAMP")]
    assert not out, f"outputs still commanded: {out}"
    tags_seen = sorted(a["tag"] for a in s["alarm_list"])
    time.sleep(2.0)
    r.plant_up()
    time.sleep(2.0)
    r.fault("estop", False)
    r.cmd("reset")
    time.sleep(1.0)
    r.cmd("reset")
    _, s = r.wait(lambda s: s["irr_step"] == 0 and not s["alarm_list"], 10, "IDLE after plant back + RESET")
    return (f"plant killed during SHOT → step 99 with A00 after {t:.2f} s, all field outputs off; "
            f"latched {' '.join(tags_seen)}; "
            f"plant restarted + RESET → IDLE, no alarms")


TESTS = [
    ("OPL-02", "Load on Runtime v4, comms, heartbeat, %MW map", opl02_comms),
    ("OPL-03", "Irrigation cycle at 1x (IRR-07, FE)", opl03_cycle),
    ("OPL-04", "E-stop during SHOT (SAF-01)", opl04_estop),
    ("OPL-05", "EC analyser wire break during SHOT (SAF-14b)", opl05_analyser),
    ("OPL-06", "Vent positioner over remote I/O (CLI-03)", opl06_positioner),
    ("OPL-07", "Setpoint clamp and read-back (IRR-15)", opl07_setpoints),
    ("OPL-08", "Plant (remote I/O) lost during SHOT (COM-01)", opl08_plant_loss),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plc", default="127.0.0.1:502", help="runtime Modbus server")
    ap.add_argument("--plant-port", type=int, default=5021)
    ap.add_argument("--clock", default="10:00", help="plant time of day (inside the day window)")
    ap.add_argument("--only", nargs="*", help="run only these IDs, e.g. OPL-04")
    ap.add_argument("--json", help="write the results here")
    a = ap.parse_args()
    host, _, port = a.plc.rpartition(":")
    r = Rig((host, int(port)), a.plant_port, a.clock)
    print(f"plant on 0.0.0.0:{a.plant_port} ({a.clock}, clear); runtime {a.plc}; waiting for the PLC to poll it")
    time.sleep(3.0)
    results = []
    for tid, title, fn in TESTS:
        if a.only and tid not in a.only:
            continue
        t = time.monotonic()
        try:
            detail, ok = fn(r), True
        except Exception as e:          # noqa: BLE001 - report and carry on
            detail, ok = f"{type(e).__name__}: {e}", False
        results.append({"id": tid, "title": title, "result": "PASS" if ok else "FAIL",
                        "detail": detail, "seconds": round(time.monotonic() - t, 1)})
        print(f"{tid} {'PASS' if ok else 'FAIL'} ({results[-1]['seconds']} s) {title}\n    {detail}", flush=True)
    try:
        r.to_idle()
        r.cmd("start")                   # leave the program enabled, as after power-up
    except Exception:                    # noqa: BLE001
        pass
    r.ps.stop()
    summary = {"date": time.strftime("%Y-%m-%d %H:%M"), "host": platform.platform(),
               "python": platform.python_version(), "runtime": a.plc, "results": results}
    if a.json:
        Path(a.json).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(x["result"] == "PASS" for x in results)
    print(f"\n{passed} / {len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
