import pytest

from farmsim.bench import Bench


def ready(b: Bench) -> Bench:
    """Let analog inputs settle, then clear power-up alarms."""
    b.run(2.0)
    b.hmi("reset")
    b.run(0.5)
    assert b.alarm_list() == [], b.alarm_list()
    return b


def make(clock="05:30", scenario="clear", short_shots=True, enabled=True, **kw) -> Bench:
    b = Bench(clock=clock, scenario=scenario, **kw)
    b.vm["irr_enabled"] = enabled      # before the first scan, so no cold-start shot
    if short_shots:                    # 20 L shots keep cycle tests short
        for z in range(1, 5):
            b.setpoint(f"SP_SHOT_Z{z}", 20)
    return ready(b)


@pytest.fixture
def night():
    """05:30, before the irrigation window: IDLE, climate in VENT."""
    return make("05:30")


@pytest.fixture
def day():
    """10:30 on a clear day, irrigation program disabled so tests start cycles explicitly."""
    b = make("10:30", enabled=False)
    assert b.step == 0 and not b.vm["irr_enabled"]
    return b


def start_cycle(b: Bench, timeout=120.0):
    b.hmi("irrigate_now")
    b.run_until(lambda b: b.step == 10, 2.0, "PRE-MIX")
    b.run_until(lambda b: b.step == 20, timeout, "first SHOT")


def finish_cycle(b: Bench, timeout=1500.0):
    b.run_until(lambda b: b.step == 0, timeout, "cycle end")


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="run slow (full-day) simulations")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow: use --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
