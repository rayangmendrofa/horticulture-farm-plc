"""FAT - safety and protection (PRD 6.4, FDS 11, 12)."""
import pytest

from conftest import make, start_cycle
from farmsim import tags
from farmsim.plant import vapour_gm3

FIELD_DO = [t for t in tags.DO_TAGS if not t.startswith("LAMP")]


def manual_irr(b):
    b.hmi("irr_manual")
    b.run(0.5)
    assert b.vm["irr_manual"]


def test_saf01_estop_all_off_latched_no_restart(day):
    b = day
    start_cycle(b)
    b.fault("estop")
    b.run(0.2)
    assert not any(b.vm[t] for t in FIELD_DO)
    assert all(b.vm[t] == 0 for t in tags.AO_TAGS)
    assert b.step == 99 and b.alarm(0)
    assert all(b.vm[f"ST_ILK_{g.upper()}"] & 1 for g in tags.ILK_GROUPS)
    b.hmi("reset")                                  # E-stop still pressed: stays latched
    b.run(1)
    assert b.alarm(0) and b.step == 99
    b.fault("estop", False)
    b.run(5)
    assert b.step == 99 and b.alarm(0), "no automatic restart after release"
    b.hmi("reset")
    b.run(1)
    assert b.step == 0 and not b.alarm(0)
    b.run(30)
    assert b.step == 0


def test_saf02_dry_run_protection(day):
    b = day
    start_cycle(b)
    b.fault("lsl201_dry")
    b.run(0.1)
    assert not b.vm["P201"] and "LSL-201 dry (dry-run protection)" in b.ilk("pump")
    b.run(2.5)
    assert b.alarm(2) and b.step == 99


def test_saf03_pressure_high_and_low(day):
    b = day
    start_cycle(b)
    b.fault("blocked_line")
    b.run_until(lambda b: b.alarm(5), 5, "A05 pressure high")
    b.run(0.2)
    assert not b.vm["P201"] and b.step == 99
    assert "A05 pressure high - RESET required" in b.ilk("pump")
    b.fault("blocked_line", False)
    b.hmi("reset")
    b.run(1)
    start_cycle(b)
    b.fault("burst_pipe")
    t0 = b.t
    b.run_until(lambda b: b.alarm(6), 20, "A06 pressure low")
    assert b.t - t0 >= 15.0
    b.run(0.2)
    assert b.step == 99


def test_saf04_pump_needs_a_flow_path(night):
    b = night
    manual_irr(b)
    b.manual_irr("P201", "XV401")
    b.run(2)
    assert b.vm["P201"]
    b.manual_irr("P201")
    b.run(0.1)
    assert not b.vm["XV401"] and not b.vm["P201"]
    assert "No flow path open (dead-head)" in b.ilk("pump")


def test_saf05_dosing_needs_pump_and_flow(night):
    b = night
    manual_irr(b)
    b.manual_irr(dose_a=50.0, dose_b=50.0, dose_acid=20.0)
    b.run(2)
    assert not any(b.vm[t] for t in ("P311", "P312", "P313"))
    assert "P-201 not running" in b.ilk("dose_ab") and "P-201 not running" in b.ilk("acid")
    b.manual_irr("P201", "XV301", dose_a=50.0, dose_b=50.0, dose_acid=20.0)
    b.run(2.0)
    assert not b.vm["P311"] and "Flow < 500 L/h" in b.ilk("dose_ab"), "flow must be established 3 s"
    b.run(3.0)
    assert b.vm["P311"] and b.vm["P312"] and b.vm["P313"]


def test_saf06_stock_low_stops_both_a_and_b(day):
    b = day
    start_cycle(b)
    assert b.vm["P311"] and b.vm["P312"]
    b.fault("stock_b_empty")
    b.run(0.1)
    assert not b.vm["P311"] and not b.vm["P312"] and b.vm["P313"]
    b.run(2.5)
    assert b.alarm(12)


def test_saf07_ec_high_high_blocks_zones_and_ab(night):
    b = night
    manual_irr(b)
    b.manual_irr("P201", "XV301", dose_a=100.0, dose_b=100.0)
    b.run_until(lambda b: b.alarm(7), 60, "A07 EC high-high")
    b.run(0.1)
    assert not b.vm["P311"] and not b.vm["P312"]
    b.manual_irr("P201", "XV301", "XV401")
    b.run(1)
    assert not b.vm["XV401"] and "A07 EC high-high - RESET required" in b.ilk("zone")


def test_saf08_ph_low_low_blocks_zones_and_acid(night):
    b = night
    manual_irr(b)
    b.manual_irr("P201", "XV301", dose_acid=100.0)
    b.run_until(lambda b: b.alarm(8), 60, "A08 pH low-low")
    b.run(0.1)
    assert not b.vm["P313"] and "pH invalid or A08" in b.ilk("acid")
    b.manual_irr("P201", "XV301", "XV402")
    b.run(1)
    assert not b.vm["XV402"] and "A08 pH low-low - RESET required" in b.ilk("zone")


def test_saf09_fans_only_with_vents_closed(night):
    b = night
    b.hmi("clim_manual")
    b.manual_clim("F601", "F602", vent=0.0)
    b.run_until(lambda b: b.vm["F601"] and b.vm["F602"], 200, "fans with vents closed")
    b.plant.vent_pos = 20.0                         # vent opened by hand-crank
    b.run(0.1)
    assert not b.vm["F601"] and not b.vm["F602"] and "Vents not closed" in b.ilk("fan")


def test_saf10_reversing_contactors_never_together(night):
    b = night
    b.hmi("clim_manual")
    b.manual_clim(vent=90.0)
    b.run(20)
    assert b.vm["M511_OPEN"]
    b.manual_clim(vent=10.0)
    gap, last_open = None, b.t
    for _ in range(int(5 / b.dt)):
        b.tick()
        assert not (b.vm["M511_OPEN"] and b.vm["M511_CLOSE"])
        if b.vm["M511_OPEN"]:
            last_open = b.t
        if b.vm["M511_CLOSE"] and gap is None:
            gap = b.t - last_open
    assert gap is not None and gap >= 0.5
    assert b.status["m511_rev"] >= 1


def test_saf11_travel_faults_lock_out(night):
    b = night
    b.hmi("clim_manual")
    b.fault("vent_stuck")
    b.manual_clim(vent=90.0)
    b.run_until(lambda b: b.alarm(36), 20, "A36 vent travel fault")
    b.run(0.1)
    assert not b.vm["M511_OPEN"] and "A36 travel lock-out" in b.ilk("vent_open")
    b.fault("vent_stuck", False)
    b.run(5)
    assert not b.vm["M511_OPEN"], "locked out until RESET"
    b.hmi("reset")
    b.run(2)
    assert b.vm["M511_OPEN"]
    b.fault("net_stuck")
    b.manual_clim("NET_DEPLOY", vent=b.plant.vent_pos)
    b.run_until(lambda b: b.alarm(37), 155, "A37 net travel fault")
    b.run(0.1)
    assert not b.vm["M521_CLOSE"]


def test_saf12_motor_protection_lock_out(night):
    b = night
    b.hmi("clim_manual")
    b.fault("m511_overload")
    b.manual_clim(vent=90.0)
    b.run(1.5)
    assert b.alarm(38) and not b.vm["M511_OPEN"]
    assert b.status["devices"][10]["motor_trip"]
    b.fault("m511_overload", False)
    b.run(2)
    assert not b.vm["M511_OPEN"]
    b.hmi("reset")
    b.run(2)
    assert b.vm["M511_OPEN"]


def test_saf13_motor_discrepancy_trips_and_locks_out(day):
    b = day
    start_cycle(b)
    b.fault("p201_trip")
    b.run(2.5)
    assert b.alarm(4) and b.step == 99
    b.fault("p201_trip", False)
    b.hmi("reset")
    b.run(1)
    assert not b.alarm(4)


def test_saf13b_fan_lockout_replaced_by_next_fan():
    b = make("10:30", enabled=False)
    b.setpoint("SP_VENT_T", 21.0)
    b.setpoint("SP_COOL_T", 22.0)
    b.run_until(lambda b: b.clim == 30, 600, "COOL")
    b.run_until(lambda b: b.vm["fan_stage"] == 2, 70)
    b.fault("f602_trip")
    b.run(3)
    assert b.alarm(41)
    b.run(0.2)
    assert b.vm["F601"] and not b.vm["F602"] and b.vm["F603"], "F-603 replaces locked-out F-602"


def test_saf14_signal_fault_fallbacks(hot_day=None):
    b = make("10:30", enabled=False)
    b.setpoint("SP_COOL_T", 40.0)
    b.run(60)
    b.fault("tt501_break")
    b.run(1.5)
    assert b.alarm(32) and b.vm["temp_dem"] == 50.0 and b.status["clim_flags"]["temp_fallback"]
    b.fault("tt501_break", False)
    b.fault("zt511_break")
    b.run(1.5)
    assert b.alarm(35)
    assert b.vm["pos_open"] == (b.vm["vent_sp"] >= 50.0)
    b.fault("zt511_break", False)
    b.fault("st101_break")
    b.run(1.5)
    assert b.alarm(30) and b.vm["storm_act"] and b.vm["vent_sp"] == 0.0
    b.fault("st101_break", False)
    b.fault("rt101_break")
    b.run(2)
    s = b.vm["rad_sum"]
    b.run(30)
    assert b.alarm(29) and b.vm["rad_sum"] == s, "radiation sum frozen"


def test_saf14b_analyser_fault_trips_irrigation(day):
    b = day
    start_cycle(b)
    b.fault("ec_break")
    b.run(1.5)
    assert b.alarm(23) and b.step == 99
    assert not b.vm["P311"] and "EC signal fault or A07" in b.ilk("dose_ab")


def test_saf15_storm_and_failed_weather_sensors(night):
    b = night
    b.hmi("clim_manual")
    b.weather(wind=16.0)
    b.manual_clim("NET_DEPLOY", vent=80.0)
    b.run(2)
    assert not b.vm["M521_CLOSE"] and "Storm wind / wind sensor fault" in b.ilk("net_deploy")
    assert b.vm["vent_sp"] == 0.0, "weather limits also cap the manual vent position"
    b.weather(wind=None)
    b.hmi("clim_auto")
    b.fault("rain_wire_break")                       # NC rain detector: open wire = rain
    b.run(1)
    assert b.status["clim_flags"]["rain"] and b.vm["vent_sp"] <= 10.0


def test_saf16_fog_and_pad_protection(night):
    b = night
    b.hmi("clim_manual")
    b.manual_clim("P541", "P531", vent=b.plant.vent_pos)
    b.plant.c_in = vapour_gm3(b.plant.t_in, 95.0)
    b.run(1)
    assert not b.vm["P541"] and "Greenhouse RH >= 90 %" in b.ilk("fog")
    b.fault("mt501_break")
    b.run(1)
    assert "MT-501 signal fault" in b.ilk("fog")
    assert b.vm["P531"]
    b.fault("pad_sump_low")
    b.run(0.1)
    assert not b.vm["P531"] and "Pad sump low" in b.ilk("pad")
    b.run(5.5)
    assert b.alarm(44)
