"""FAT - one full simulated day (PRD 10.2 acceptance, NFR-09). About 10 min of CPU:
run with ``pytest --runslow`` (CI does)."""
import pytest

from conftest import make


@pytest.mark.slow
def test_day01_clear_day_05_to_19():
    b = make("05:00", short_shots=False)
    max_t, switches, last = 0.0, 0, b.clim
    shots_in_band = True
    while b.plant.clock_min < 19 * 60:
        b.tick()
        max_t = max(max_t, b.plant.t_in)
        cooling = b.clim in (20, 25, 30, 40)
        if cooling != (last in (20, 25, 30, 40)):
            switches += 1
        last = b.clim
        if b.step == 20 and b.vm["zone_open_secs"] >= 30:
            shots_in_band &= abs(b.plant.ec_true - 2.5) <= 0.2 and abs(b.plant.ph_true - 5.8) <= 0.3
    st = b.status
    assert max_t <= 35.0, max_t                         # NFR-09
    assert switches <= 4, switches                      # VENT <-> COOL switching
    assert shots_in_band                                # every shot in band
    assert st["cycles_day"] >= 10 and st["irr_step_name"] == "IDLE"
    assert b.alarm_list() == [], b.alarm_list()         # PRD 10.2: no alarms
