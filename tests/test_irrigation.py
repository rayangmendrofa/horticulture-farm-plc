"""FAT - irrigation (PRD 6.1, FDS 6)."""
import pytest

from conftest import finish_cycle, make, start_cycle


def test_irr01_start_stop_enable_program(night):
    b = night
    b.hmi("stop")                                   # STOP in IDLE disables the program
    b.run(0.5)
    assert not b.vm["irr_enabled"]
    b.plant.set_clock("08:00")                      # in window, max interval long passed
    b.run(70)
    assert b.step == 0, "no automatic cycle with the program disabled"
    b.hmi("start")
    b.run_until(lambda b: b.step == 10, 2.0, "cycle start after START")
    assert b.vm["irr_enabled"]
    assert b.status["irr_flags"]["enabled"]


def test_irr02_radiation_sum_start_respects_min_interval(day):
    b = day
    b.weather(rad=800.0)
    b.vm["min_since"] = 10                          # below the 20 min minimum interval
    b.vm["rad_sum"] = 150.0                         # threshold reached
    b.hmi("start")
    b.run(30)
    assert b.step == 0, "minimum interval must hold back a radiation start"
    b.vm["min_since"] = 25
    b.vm["rad_sum"] = 129.0                         # threshold 130; 800 W/m2 adds 0.08 J/cm2 per s
    b.run(5)
    assert b.step == 0
    t = b.run_until(lambda b: b.step == 10, 30, "radiation start")
    assert b.vm["rad_sum"] < 1.0 and b.vm["min_since"] == 0, "sum and interval restart at cycle start"
    assert t > 0


def test_irr03_max_interval_start_without_radiation(day):
    b = day
    b.weather(rad=0.0)
    b.vm["rad_sum"] = 0.0
    b.vm["min_since"] = 119
    b.hmi("start")
    b.run(2)
    assert b.step == 0
    b.run_until(lambda b: b.step == 10, 65, "max-interval start")


def test_irr04_no_start_outside_window_or_after_max_cycles(day):
    b = day
    b.hmi("start")
    b.plant.set_clock("18:00")                      # window ends 17:00
    b.vm["min_since"] = 500
    b.run(70)
    assert b.step == 0 and not b.status["irr_flags"]["in_window"]
    b.plant.set_clock("12:00")
    b.vm["cycles_day"] = 30                         # SP_MAX_CYCLES
    b.run(70)
    assert b.step == 0 and b.status["irr_flags"]["max_cycles"]
    b.vm["cycles_day"] = 29
    b.run_until(lambda b: b.step == 10, 2, "start once below max cycles")


def test_irr05_first_cycle_at_window_start():
    b = make("06:28")                               # cold start: min_since = SP_MAX_INT
    assert b.step == 0
    b.run_until(lambda b: b.step == 10, 200, "morning start shot")
    assert b.plant.clock_min == 390                 # 06:30


def test_irr06_irrigate_now_ignores_window_and_enable():
    b = make("20:00", enabled=False)
    assert b.step == 0
    start_cycle(b)
    finish_cycle(b)
    assert b.status["cycles_day"] == 1


def test_irr07_cycle_sequence_skips_disabled_zones(day):
    b = day
    b.setpoint("SP_ZONE_EN", 0b0101)                # Z1 and Z3
    seen, steps = [], []
    start_cycle(b)
    while b.step != 0:
        b.tick()
        z = b.vm["zone"]
        if z and (not seen or seen[-1] != z):
            seen.append(z)
        if not steps or steps[-1] != b.step:
            steps.append(b.step)
    assert seen == [1, 3]
    assert steps == [20, 40, 0]
    assert not any(b.vm[t] for t in ("XV402", "XV404"))


def test_irr08_shot_volume_within_2_percent():
    b = make("10:30", short_shots=False, enabled=False)   # default 60 L shots
    start_cycle(b)
    finish_cycle(b)
    for z, litres in enumerate(b.plant.supplied_l, start=1):
        assert litres == pytest.approx(60.0, rel=0.02), f"Z{z} got {litres:.2f} L"


def test_irr09_open_before_close_and_never_dead_headed(day):
    b = day
    start_cycle(b)
    both_open, deadhead = 0.0, 0
    while b.step != 0:
        b.tick()
        if b.vm["XV401"] and b.vm["XV402"]:
            both_open += b.dt
        if b.vm["P201"] and not (b.vm["XV301"] or b.vm["XV401"] or b.vm["XV402"]
                                 or b.vm["XV403"] or b.vm["XV404"]):
            deadhead += 1
    assert both_open == pytest.approx(2.0, abs=0.1)
    assert deadhead == 0


def test_irr10_stop_pauses_and_resume_delivers_remaining_volume(day):
    b = day
    start_cycle(b)
    b.run_until(lambda b: b.vm["zone"] == 2 and b.vm["zone_vol"] >= 10.0, 300, "Z2 half way")
    b.hmi("stop")
    b.run(1.0)
    assert b.step == 80
    assert not any(b.vm[t] for t in ("P201", "XV301", "XV402", "P311", "P312", "P313"))
    b.run(30)
    assert b.status["irr_flags"]["resume_pending"]
    b.hmi("start")
    b.run_until(lambda b: b.step == 10, 2, "PRE-MIX on resume")
    b.run_until(lambda b: b.step == 20, 120, "SHOT on resume")
    assert b.vm["zone"] == 2 and b.vm["zone_vol"] >= 10.0
    finish_cycle(b)
    assert b.plant.supplied_l[1] == pytest.approx(20.0, abs=2.0)   # + uncounted overlaps


def test_irr11_abort_cancels_paused_cycle(day):
    b = day
    start_cycle(b)
    b.hmi("stop")
    b.run(0.5)
    assert b.step == 80
    b.hmi("abort")
    b.run(0.5)
    assert b.step == 0 and b.vm["zone"] == 0 and not b.vm["resume"]


def test_irr12_radiation_sum_accuracy(day):
    b = day
    b.weather(rad=500.0)
    b.run(2)
    b.vm["rad_sum"] = 0.0
    b.run(100.0)
    assert b.vm["rad_sum"] == pytest.approx(5.0, rel=0.005)     # NFR-04: 0.5 %


def test_irr13_midnight_rollover():
    b = make("23:58", enabled=False)
    b.vm["cycles_day"] = 7
    b.vm["water_day"] = 512.0
    b.vm["z1_supply"] = 100.0
    b.vm["drain_l"] = 25.0
    b.run_until(lambda b: b.plant.clock_min == 1, 200, "00:01")
    st = b.status
    assert (st["cycles_prev"], st["water_prev"], st["drain_prev"]) == (7, 512, 25.0)
    assert (st["cycles_day"], st["water_day"], st["drain_day"]) == (0, 0, 0.0)


def test_irr14_tank_refill_hysteresis(night):
    b = night
    b.plant.tank_v = 0.41 * b.plant.cfg.tank_l
    b.run(5)
    assert not b.vm["XV201"]
    b.plant.tank_v = 0.395 * b.plant.cfg.tank_l
    b.run(2)
    assert b.vm["XV201"]
    b.plant.tank_v = 0.845 * b.plant.cfg.tank_l
    b.run_until(lambda b: not b.vm["XV201"], 60, "refill stops at 85 %")
    assert b.plant.level_pct == pytest.approx(85.0, abs=0.2)


def test_irr15_setpoints_clamped_and_written_back(night):
    b = night
    b.vm["SP_EC"] = 1000
    b.vm["SP_DAY_START"] = 600
    b.vm["SP_DAY_END"] = 610
    b.vm["SP_COOL_T"] = 250                          # below vent SP + 1 degC
    b.vm["SP_ZONE_EN"] = 0xFF
    b.run(0.1)
    assert b.vm["SP_EC"] == 400
    assert b.vm["SP_DAY_END"] == 630
    assert b.vm["SP_COOL_T"] == 290
    assert b.vm["SP_ZONE_EN"] == 0x0F


def test_irr16_manual_only_from_idle_or_fault(day):
    b = day
    start_cycle(b)
    b.hmi("irr_manual")
    b.run(0.5)
    assert not b.vm["irr_manual"] and b.step == 20
    b.hmi("stop")
    b.run(0.5)
    b.hmi("abort")
    b.run(0.5)
    b.hmi("irr_manual")
    b.run(0.5)
    assert b.vm["irr_manual"] and b.status["irr_flags"]["manual"]
    b.manual_irr("P201")                             # no flow path: blocked
    b.run(1)
    assert not b.vm["P201"] and "No flow path open (dead-head)" in b.ilk("pump")
    b.manual_irr("P201", "XV301")
    b.run(2)
    assert b.vm["P201"] and b.plant.q_pump > 1.0
    b.hmi("irr_auto")
    b.run(0.5)
    assert not b.vm["irr_manual"] and not b.vm["P201"] and b.vm["HMI_MAN_IRR"] == 0


def test_irr17_clock_fault_uses_daylight_window():
    b = make("10:00", enabled=False)
    b.fault("clock_frozen")
    b.plant.frozen_clock = 300                       # frozen at 05:00, outside the window
    b.run_until(lambda b: b.alarm(1), 160, "A01 clock fault")
    assert not b.status["irr_flags"]["in_window"] or b.status["irr_flags"]["daylight_fallback"]
    b.run(300)                                      # daylight for 5 min
    assert b.status["irr_flags"]["daylight_fallback"] and b.status["irr_flags"]["in_window"]
    b.weather(rad=0.0)
    b.run(1)
    assert not b.status["irr_flags"]["in_window"]
