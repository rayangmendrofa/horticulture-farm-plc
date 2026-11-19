"""FAT - fertigation (PRD 6.2, FDS 7)."""
import pytest

from conftest import finish_cycle, start_cycle


def test_fer01_dosing_only_while_pumping_and_ab_equal(day):
    b = day
    assert not any(b.vm[t] for t in ("P311", "P312", "P313"))
    b.hmi("irrigate_now")
    seen_steps, scans_in_40 = set(), 0
    while True:
        b.tick()
        s = b.step
        scans_in_40 = scans_in_40 + 1 if s == 40 else 0
        dosing = b.vm["P311"] or b.vm["P312"] or b.vm["P313"]
        if dosing and scans_in_40 != 1:
            seen_steps.add(s)
            assert b.vm["P311_REF"] == b.vm["P312_REF"], "A and B run 1 : 1"
        if scans_in_40 > 1:                          # outputs follow the step one scan later
            assert not dosing, "no dosing in RUN-DOWN"
        if s == 0 and b.t > 30:
            break
    assert seen_steps <= {10, 20, 25} and {10, 20} <= seen_steps


def _band_stats(b, settle_s=30.0):
    """EC/pH min/max at the sensors during SHOT, once each zone has run settle_s."""
    ec, ph = [], []
    while b.step != 0:
        b.tick()
        if b.step == 20 and b.vm["zone_open_secs"] >= settle_s:
            ec.append(b.plant.ec_true)
            ph.append(b.plant.ph_true)
    return min(ec), max(ec), min(ph), max(ph)


def test_fer02_fer03_ec_ph_reach_band_and_hold(day):
    b = day
    for z in range(1, 5):
        b.setpoint(f"SP_SHOT_Z{z}", 40)
    b.hmi("irrigate_now")
    b.run_until(lambda b: b.step == 10, 2)
    t0 = b.t
    b.run_until(lambda b: b.vm["in_band"], 60, "EC and pH in band")
    assert b.t - t0 <= 60.0                          # FE-02 / FE-03: band within 60 s
    ec_lo, ec_hi, ph_lo, ph_hi = _band_stats(b)
    assert 2.45 <= ec_lo and ec_hi <= 2.55, (ec_lo, ec_hi)      # SP 2.50 +- 0.05
    assert 5.70 <= ph_lo and ph_hi <= 5.90, (ph_lo, ph_hi)      # SP 5.80 +- 0.10
    assert b.alarm_list() == []


def test_fer04_zone_opens_only_after_10s_in_band(day):
    b = day
    b.hmi("irrigate_now")
    in_band_since = None
    while not (b.vm["XV401"]):
        b.tick()
        if b.vm["in_band"]:
            in_band_since = in_band_since if in_band_since is not None else b.t
        else:
            in_band_since = None
    assert in_band_since is not None and b.t - in_band_since >= 10.0


def test_fer05_out_of_band_goes_to_hold_and_continues(day):
    b = day
    start_cycle(b)
    b.run_until(lambda b: b.vm["zone_vol"] >= 5.0, 120)
    b.setpoint("SP_EC", 3.0)                          # now 0.5 mS/cm out of band
    b.run_until(lambda b: b.step == 25, 30, "HOLD")   # after 10 s out of band
    vol = b.vm["zone_vol"]
    b.run(5)
    assert b.vm["XV301"] and not b.vm["XV401"], "back to recirculation, zone closed"
    assert b.vm["zone_vol"] == pytest.approx(vol, abs=0.01), "volume kept, not counted in HOLD"
    b.run_until(lambda b: b.step == 20, 120, "back to SHOT")
    assert b.vm["zone"] == 1
    finish_cycle(b)
    assert b.alarm_list() == []


def test_fer06_band_timeout_trips(day):
    b = day
    b.fault("stock_a_empty")                         # A/B blocked: EC never reaches band
    b.hmi("irrigate_now")
    b.run_until(lambda b: b.step == 99, 200, "FAULT")
    assert b.alarm(10) and b.alarm(11)               # A10 band timeout, A11 stock A low
    assert not b.vm["P311"] and not b.vm["P312"]


def test_fer07_one_ph_probe_failed_uses_the_other(day):
    b = day
    b.fault("ph_a_break")
    b.run(2)
    assert b.alarm(24) and not b.alarm(26)
    start_cycle(b)
    finish_cycle(b)
    assert b.vm["ph"] == pytest.approx(b.plant.ph_true, abs=0.05)
    assert b.alarm_list() == ["A24"] and b.status["cycles_day"] == 1


def test_fer08_ph_deviation_and_both_probes_lost_trip(day):
    b = day
    b.fault("ph_b_drift")                            # probe B reads 0.6 high
    b.hmi("irrigate_now")
    b.run_until(lambda b: b.step == 99, 30, "trip on deviation (10 s), during PRE-MIX")
    assert b.alarm(9)
    assert not b.vm["P313"] and "pH invalid or A08" in b.ilk("acid")
    b.fault("ph_b_drift", False)
    b.fault("ph_a_break")
    b.fault("ph_b_break")
    b.run(2)
    assert b.alarm(26)                               # A26 pH measurement lost: trip class
    assert not b.vm["ph_valid"]


def test_fer09_setpoint_change_during_shot(day):
    b = day
    for z in range(1, 5):
        b.setpoint(f"SP_SHOT_Z{z}", 60)
    start_cycle(b)
    b.run(20)
    b.setpoint("SP_PH", 6.0)                          # 0.2 away: still in band, no HOLD
    b.run(60)
    assert b.step == 20
    assert b.plant.ph_true == pytest.approx(6.0, abs=0.1)
