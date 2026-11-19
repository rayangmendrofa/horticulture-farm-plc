"""Fault knowledge base, troubleshooting guide, subtle faults and the HMI trainer (FLT)."""
import sys
from pathlib import Path

import pytest
from conftest import make, start_cycle

from farmsim.faults import FAULT_INFO, TRAINER_POOL
from farmsim.plant import FAULTS, FIELD_CHECKS, SUBTLE, Plant

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gen_troubleshooting  # noqa: E402

SUBTLE_FAULTS = [k for k, v in FAULT_INFO.items() if v["level"] == 3]


def test_flt01_knowledge_base_covers_every_fault():
    assert set(FAULT_INFO) == set(FAULTS) and len(FAULTS) == 48
    for key, f in FAULT_INFO.items():
        assert f["level"] in (1, 2, 3), key
        for field in ("title", "symptoms", "checks", "cause", "fix"):
            assert len(f[field]) > 10, (key, field)
    assert "estop" not in TRAINER_POOL and len(TRAINER_POOL) == 47
    assert set(SUBTLE) <= set(SUBTLE_FAULTS)


def test_flt02_troubleshooting_guide_is_current():
    """docs/TROUBLESHOOTING.md is generated: regenerate it after editing farmsim/faults.py."""
    text = (ROOT / "docs" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
    assert text == gen_troubleshooting.render(), "run: python tools/gen_troubleshooting.py"
    for f in FAULT_INFO.values():
        assert f"### {f['title']}\n" in text


def test_flt03_field_checks_reveal_mechanical_faults():
    p = Plant()
    assert p.field_checks() == (1 << len(FIELD_CHECKS)) - 1            # all normal
    for fault, check in (("xv301_passing", "Return line quiet"), ("stock_a_weak", "Stock tank A"),
                         ("z2_partly_clogged", "Zone 2 drippers"), ("rain_wire_break", "Rain sensor")):
        p.faults = {fault}
        i = next(n for n, t in enumerate(FIELD_CHECKS) if t.startswith(check))
        assert not p.field_checks() >> i & 1, fault


def shot_cycle(fault=None):
    """One irrigation cycle (4 x 20 L) at 10:30; returns delivered volumes, shot times, dosing, EC."""
    b = make("10:30", enabled=False)
    if fault:
        b.fault(fault)
    b.run(30)
    start_cycle(b)
    sup0, t0, shot_s, dose, ec_true, ec_meas = list(b.plant.supplied_l), {}, {}, [], [], []
    while b.step != 0:
        b.tick()
        if b.step == 20:
            z = b.vm["zone"]
            t0.setdefault(z, b.t)
            shot_s[z] = b.t - t0[z]
            if b.vm["zone_open_secs"] > 20:
                dose.append(b.vm["dose_a"])
                ec_true.append(b.plant.ec_true)
                ec_meas.append(b.vm["ec"])
    assert b.alarm_list() == [], b.alarm_list()      # subtle faults raise no alarm at all
    avg = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return dict(supplied=[x - y for x, y in zip(b.plant.supplied_l, sup0)], shot_s=shot_s,
                dose=avg(dose), ec_true=avg(ec_true), ec_meas=avg(ec_meas))


@pytest.fixture(scope="module")
def normal():
    return shot_cycle()


def test_flt04_ec_drift_starves_the_crop_without_alarm():
    r = shot_cycle("ec_reads_high")
    assert r["ec_meas"] == pytest.approx(2.5, abs=0.1)
    assert r["ec_true"] == pytest.approx(2.1, abs=0.1)


def test_flt05_short_water_without_alarm(normal):
    """FT-201 reading high and XV-301 passing both under-water every zone by about 15 %."""
    for fault in ("ft201_reads_high", "xv301_passing"):
        r = shot_cycle(fault)
        for got, ref in zip(r["supplied"], normal["supplied"]):
            assert 0.78 * ref <= got <= 0.90 * ref, (fault, got, ref)
    assert shot_cycle("xv301_passing")["dose"] > 1.1 * normal["dose"], "passing return valve raises dosing"


def test_flt06_partly_clogged_zone_waters_longer(normal):
    r = shot_cycle("z2_partly_clogged")
    assert r["shot_s"][2] > 1.15 * r["shot_s"][1]
    assert r["shot_s"][1] == pytest.approx(normal["shot_s"][1], rel=0.05)


def test_flt07_weak_stock_raises_dosing(normal):
    r = shot_cycle("stock_a_weak")
    assert r["dose"] > 1.2 * normal["dose"]
    assert r["ec_true"] == pytest.approx(2.5, abs=0.1), "EC is in band: only the ratio is wrong"


def test_flt08_tt501_drift_reads_low_without_alarm():
    b = make("12:30", enabled=False)
    b.fault("tt501_reads_low")
    b.run(60)
    assert b.vm["t_in"] == pytest.approx(b.plant.t_in - 3.0, abs=0.2)
    assert b.alarm_list() == []


def test_flt09_trainer_challenge(monkeypatch):
    from test_hmi import Rig
    rig = Rig("10:30")
    try:
        rig.run(2)
        monkeypatch.setattr(rig.backend.rng, "choice", lambda pool: "xv301_passing")
        assert rig.post("/api/trainer", {"action": "start"})[0] == 200
        rig.run(2)
        sim = rig.get()["sim"]
        assert rig.ps.plant.faults == {"xv301_passing"}
        assert sim["faults"] == [] and "ec" not in sim["truth"] and "field" not in sim, "fault hidden"
        assert rig.post("/api/sim", {"fault": "estop", "active": True})[0] == 400, "injection locked"
        rig.post("/api/trainer", {"action": "hint"})
        rig.run(1)
        sim = rig.get()["sim"]
        assert "ec" in sim["truth"] and not sim["field"]["Return line quiet with XV-301 closed (no flow through the seat)"]
        code, body = rig.post("/api/trainer", {"action": "answer", "fault": "xv301_passing"})
        assert code == 200 and body["result"]["correct"] and body["result"]["hints"] == 1
        rig.run(2)
        assert rig.ps.plant.faults == set() and rig.get()["trainer"]["result"]["correct"]
        assert rig.post("/api/trainer", {"action": "hint"})[0] == 400, "no challenge running"
        rig.post("/api/trainer", {"action": "start"})
        code, body = rig.post("/api/trainer", {"action": "answer", "fault": "ec_reads_high"})
        assert not body["result"]["correct"] and body["result"]["title"] == FAULT_INFO["xv301_passing"]["title"]
    finally:
        rig.close()
