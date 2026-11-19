"""FAT - device blocks, diagnostics and maintenance (PRD 6.5, FDS 6.3, 6.5, 10, 12.3)."""
from conftest import finish_cycle, start_cycle
from farmsim import tags


def dev(b, key):
    return next(d for d in b.status["devices"] if d["key"] == key)


def test_dev01_status_words(day):
    b = day
    start_cycle(b)
    b.run(3)
    p201 = dev(b, "p201")
    assert p201["requested"] and p201["cmd"] and p201["running"] and not p201["blocked"]
    z = dev(b, "xv401")
    assert z["requested"] and z["cmd"] and z["kind"] == "valve"
    vent = dev(b, "m511")
    assert vent["kind"] == "actuator" and not vent["travel_fault"]
    assert set(tags.DEVICE_KEYS) == {d["key"] for d in b.status["devices"]}


def test_dev02_interlock_reasons_published(day):
    b = day
    b.hmi("irr_manual")
    b.run(0.5)
    b.manual_irr("P201")
    b.run(0.5)
    p201 = dev(b, "p201")
    assert p201["blocked"] and p201["interlocks"] == ["No flow path open (dead-head)"]
    b.fault("estop")
    b.run(0.2)
    for g in tags.ILK_GROUPS:
        assert "E-stop" in b.status["interlocks"][g], g


def test_dev03_zone_flow_high(day):
    b = day
    b.setpoint("SP_ZONE_EN", 0b1000)
    b.setpoint("SP_SHOT_Z4", 60)
    b.fault("z4_leak")
    start_cycle(b)
    b.run_until(lambda b: b.alarm(17), 80, "A17 flow high")
    assert b.status["zone_diag"]["Z4"]["flow_high"]
    finish_cycle(b)                                   # warning only: shot completes
    assert b.status["zone_diag"]["Z4"]["flow_high"]
    b.hmi("reset")
    b.run(0.5)
    assert not b.status["zone_diag"]["Z4"]["flow_high"] and not b.alarm(17)


def test_dev04_zone_flow_low(day):
    b = day
    b.setpoint("SP_ZONE_EN", 0b0100)
    b.setpoint("SP_SHOT_Z3", 60)
    b.fault("z3_clogged")
    start_cycle(b)
    b.run_until(lambda b: b.alarm(18), 80, "A18 flow low")
    assert b.status["zone_diag"]["Z3"]["flow_low"]


def test_dev05_shot_timeout_skips_zone(day):
    b = day
    b.setpoint("SP_ZONE_EN", 0b1100)
    b.setpoint("SP_FLOW_Z3", 2500)                    # 20 L expected in 29 s: timeout 87.6 s
    b.fault("z3_clogged")                             # real flow 690 L/h: 104 s for 20 L
    start_cycle(b)
    b.run_until(lambda b: b.vm["zone"] == 4, 200, "Z3 skipped")
    b.run(0.1)                                        # alarm latches on the next scan
    assert b.alarm(19) and b.status["zone_diag"]["Z3"]["timeout"]
    assert b.vm["zone_vol"] < 2.0
    finish_cycle(b)
    assert b.plant.supplied_l[2] < 19.0


def test_dev06_drain_percentage_alarm(day):
    b = day
    b.setpoint("SP_ZONE_EN", 0b0001)
    b.vm["cycles_day"] = 5
    b.vm["z1_supply"] = 1000.0                        # 1000 L in, almost no drain: < 10 %
    b.vm["drain_l"] = 10.0
    start_cycle(b)
    finish_cycle(b)
    b.run(0.1)
    st = b.status
    assert st["drain_day"] < 10.0 and b.alarm(28)


def test_dev07_maintenance_counters(night):
    b = night
    b.hmi("irr_manual")
    b.run(0.5)
    b.manual_irr("P201", "XV401")
    b.run(61.5)
    st = b.status
    assert st["p201_starts"] == 1 and st["p201_runmin"] == 1
    assert st["xv401_cyc"] == 1
    b.manual_irr()
    b.run(1)
    b.manual_irr("P201", "XV401")
    b.run(2)
    st = b.status
    assert st["p201_starts"] == 2 and st["xv401_cyc"] == 2


def test_dev08_stack_light(day):
    b = day
    assert b.vm["LAMP_AMBER"] and not b.vm["LAMP_GREEN"]      # program disabled
    b.hmi("start")
    b.run(1)
    assert b.vm["LAMP_GREEN"] and not b.vm["LAMP_AMBER"] and not b.vm["LAMP_RED"]
    b.fault("estop")
    b.run(1)
    assert b.vm["LAMP_RED"] and not b.vm["LAMP_GREEN"]
    b.fault("estop", False)
    seen = set()
    for _ in range(int(3 / b.dt)):
        b.tick()
        seen.add(b.vm["LAMP_RED"])
    assert seen == {True, False}, "red flashes: condition gone, RESET needed"
    b.hmi("reset")
    b.run(1)
    assert not b.vm["LAMP_RED"]
