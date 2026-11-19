"""FAT - climate (PRD 6.3, FDS 8)."""
import pytest

from conftest import make


@pytest.fixture
def hot():
    """10:30 on a clear day, irrigation disabled: vents driven by temperature."""
    return make("10:30", enabled=False)


def settle_vent(b, timeout=200.0):
    b.run_until(lambda b: abs(b.vm["vent_sp"] - b.vm["vent_pos"]) <= 2.0
                and not (b.vm["M511_OPEN"] or b.vm["M511_CLOSE"]), timeout, "vent at setpoint")


def test_cli01_vent_follows_temperature_demand(hot):
    b = hot
    b.run(120)
    assert b.plant.t_in > 28.0
    assert b.vm["temp_dem"] > b.vm["hum_dem"]
    assert b.vm["vent_sp"] == pytest.approx(b.vm["demand"], abs=0.01)
    assert b.vm["vent_sp"] > 60.0
    settle_vent(b)


def test_cli02_humidity_venting_at_night():
    b = make("03:00", enabled=False)
    b.run(300)
    assert b.plant.t_in < 28.0 and b.vm["temp_dem"] == 0.0
    rh = b.vm["rh_in"]
    assert rh > 85.0
    assert b.vm["hum_dem"] == pytest.approx(min(50.0, (rh - 85.0) * 5.0), abs=0.5)
    assert b.status["clim_flags"]["humidity_venting"]
    settle_vent(b)


def test_cli03_positioner_accuracy(night):
    b = night
    b.hmi("clim_manual")
    b.manual_clim(vent=37.0)
    b.run(1)
    settle_vent(b)
    assert b.plant.vent_pos == pytest.approx(37.0, abs=2.0)
    b.manual_clim(vent=100.0)
    b.run_until(lambda b: b.vm["ZSO511"], 150, "open limit")
    b.manual_clim(vent=0.0)
    b.run_until(lambda b: b.vm["ZSC511"], 150, "closed limit (vent sealed)")


def test_cli04_rain_limits_vents_and_releases_after_5_min(hot):
    b = hot
    b.setpoint("SP_COOL_T", 40.0)       # isolate the rain limit from the COOL changeover
    b.run(120)
    assert b.vm["vent_sp"] > 30.0
    b.weather(rain=True)
    b.run(1)
    assert b.vm["vent_sp"] <= 10.0 and b.status["clim_flags"]["rain"]
    b.run(120)
    assert b.plant.vent_pos <= 12.0
    b.weather(rain=None)
    b.run(240)
    assert b.vm["vent_sp"] <= 10.0, "still limited 4 min after the rain"
    b.run(70)
    assert b.vm["vent_sp"] > 10.0 and not b.status["clim_flags"]["rain"]


def test_cli05_wind_caps_vents_at_30(hot):
    b = hot
    b.setpoint("SP_COOL_T", 40.0)
    b.run(120)
    b.weather(wind=12.0)
    b.run(1)
    assert b.vm["vent_sp"] <= 30.0 and b.status["clim_flags"]["wind_limit"]
    b.run(120)
    assert b.plant.vent_pos <= 32.0


def test_cli06_storm_closes_vents_and_retracts_net(hot):
    b = hot
    b.plant.net_pos = 100.0                          # net deployed
    b.vm["net_dem"] = True
    b.run(60)
    assert b.vm["ZSC521"]
    b.weather(wind=16.0)
    b.run(1)
    assert b.vm["vent_sp"] == 0.0 and b.status["clim_flags"]["storm"]
    b.run_until(lambda b: b.vm["ZSC511"] and b.vm["ZSO521"], 160, "vents closed, net retracted")


def test_cli07_shade_net_deploys_and_retracts(hot):
    b = hot
    b.setpoint("SP_VENT_T", 33.0)       # temperature rules (>= 37 deploy, < 35 allow retract)
    b.setpoint("SP_COOL_T", 40.0)       #   out of the way: test the radiation rule
    b.vm["net_dem"] = False             # latched by temperature while the fixture settled
    b.plant.net_pos = 0.0
    b.weather(rad=800.0)
    b.run(9 * 60)
    assert not b.vm["net_dem"]
    b.run(70)
    assert b.vm["net_dem"]
    b.run_until(lambda b: b.vm["ZSC521"], 100, "net deployed")
    b.weather(rad=450.0)
    b.run(14 * 60)
    assert b.vm["net_dem"]
    b.run(70)
    assert not b.vm["net_dem"]
    b.run_until(lambda b: b.vm["ZSO521"], 100, "net retracted")


def test_cli08_fog_pulses_10_on_50_off(hot):
    b = hot
    b.setpoint("SP_VPD_FOG", 1.0)
    b.run(60)
    assert b.vm["vpd"] > 1.0 and b.vm["fog_dem"]
    on = 0.0
    for _ in range(int(120 / b.dt)):
        b.tick()
        on += b.dt if b.vm["P541"] else 0.0
    assert on == pytest.approx(20.0, abs=1.0)
    b.setpoint("SP_VPD_FOG", 2.5)                    # VPD now below SP - 0.3
    b.run(2)
    assert not b.vm["fog_dem"] and not b.vm["P541"]


def enter_cool(b):
    """Lower the cool setpoint so the hot house enters COOL through the real path."""
    b.setpoint("SP_VENT_T", 26.0)
    b.setpoint("SP_COOL_T", 29.0)
    b.run_until(lambda b: b.clim == 20, 400, "COOL-START")


def test_cli09_cool_entry_closes_vents_then_prewets(hot):
    b = hot
    b.run(60)
    assert b.clim == 10
    t0 = b.t
    enter_cool(b)
    assert b.t - t0 >= 300.0, "COOL condition must hold 5 min"
    while b.clim == 20:
        b.tick()
        if b.clim == 20:
            assert not b.vm["P531"] and not any(b.vm[f] for f in ("F601", "F602", "F603"))
    assert b.clim == 25 and b.vm["vents_closed"]
    assert b.vm["P531"] and not b.vm["F601"]
    b.run_until(lambda b: b.clim == 30, 61, "COOL after 60 s pre-wet")
    b.run(1)
    assert b.vm["F601"] and b.vm["P531"] and b.vm["vent_sp"] == 0.0


def test_cli10_fan_staging(hot):
    b = hot
    enter_cool(b)
    b.run_until(lambda b: b.clim == 30, 300)
    b.setpoint("SP_VENT_T", 21.0)
    b.setpoint("SP_COOL_T", 22.0)                    # far below the house: stage up
    b.run(62)
    assert b.vm["fan_stage"] == 2
    b.run(62)
    assert b.vm["fan_stage"] == 3
    b.run(1)
    assert all(b.vm[f] for f in ("F601", "F602", "F603"))
    b.setpoint("SP_VENT_T", 30.0)
    b.setpoint("SP_COOL_T", 40.0)                    # far above: stage down every 120 s
    b.run(122)
    assert b.vm["fan_stage"] == 2
    b.run(122)
    assert b.vm["fan_stage"] == 1


def test_cli11_cool_exit_and_pad_dry(hot):
    b = hot
    enter_cool(b)
    b.run_until(lambda b: b.clim == 30, 300)
    b.setpoint("SP_VENT_T", 30.0)
    b.setpoint("SP_COOL_T", 40.0)                    # house now 3 degC below: exit after 10 min
    b.run(9 * 60)
    assert b.clim == 30
    b.run_until(lambda b: b.clim == 40, 70, "PAD-DRY")
    b.run(1)
    assert not b.vm["P531"] and b.vm["F601"] and not b.vm["F602"] and not b.vm["F603"]
    b.run_until(lambda b: b.clim == 10, 301, "back to VENT after 5 min")
    b.run(1)
    assert not b.vm["F601"]


def test_cli12_climate_manual_with_interlocks(hot):
    b = hot
    b.run(60)
    b.hmi("clim_manual")
    b.manual_clim("F601", vent=50.0)
    b.run(2)
    assert b.clim == 90 and b.status["clim_flags"]["manual"]
    assert not b.vm["F601"] and "Vents not closed" in b.ilk("fan")
    b.manual_clim("F601", vent=0.0)
    b.run_until(lambda b: b.vm["F601"], 160, "fan runs once the vents are closed")
    b.manual_clim("F601", vent=50.0)
    b.run(2)
    assert not b.vm["M511_OPEN"] and "Fan commanded (pad-and-fan)" in b.ilk("vent_open")
    b.hmi("clim_auto")
    b.run(1)
    assert b.clim == 10 and b.vm["HMI_MAN_CLIM"] == 0 and not b.vm["F601"]
