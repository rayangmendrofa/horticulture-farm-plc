"""Browser demo glue: the real PLC and plant with the crop layer (WEB)."""
import json

from farmsim.crops import Bed
from farmsim.webdemo import TICKS_PER_MIN, Demo, meta


def cmd(d, **m):
    return json.loads(d.command(json.dumps(m)))


def test_web01_boot_recipe_and_state():
    d = Demo("10:30", seed=1)
    s = json.loads(d.state())
    assert s["clock"] == "10:30" and s["plc"]["alarms"] == []
    assert [z["crop"] for z in s["zones"]] == ["tomato", "cucumber", "lettuce", "chili"]
    assert s["sp"]["SP_SHOT_Z3"] == 25 and s["sp"]["SP_ZONE_EN"] == 15
    assert 2.0 < s["sp"]["SP_EC"] < 2.5, "house EC is the mean of the four crops"
    assert len(json.loads(meta())["crops"]) == 7


def test_web02_crops_grow_and_harvest():
    d = Demo("10:30", seed=1)
    assert cmd(d, cmd="plant", zone=2, crop="kangkung")["ok"]
    cmd(d, cmd="hmi", name="irrigate_now")
    d.run(30 * TICKS_PER_MIN)                       # 30 simulated minutes of daylight
    z = json.loads(d.state())["zones"]
    assert all(b["maturity"] > 0 for b in z) and z[2]["last_ec"] is not None
    d.beds[2].days = d.beds[2].target_days          # ripen kangkung
    assert cmd(d, cmd="harvest", zone=2)["kg"] > 0
    assert d.harvests == 1 and d.beds[2].crop is None and d.b.vm["SP_ZONE_EN"] == 0b1011


def test_web03_stress_hurts_health():
    bed = Bed()
    bed.plant("lettuce")
    for _ in range(60):
        bed.step_minute(t_in=36.0, rad_in=500, deficit_l=10)    # too hot for lettuce
    assert bed.health < 100 and "heat" in bed.stress


def test_web04_commands_and_challenge():
    d = Demo("10:30", seed=3)
    assert not cmd(d, cmd="nonsense")["ok"]
    assert not cmd(d, cmd="setpoint", name="SP_NOPE", value=1)["ok"]
    assert cmd(d, cmd="setpoint", name="SP_EC", value=2.0)["ok"] and d.b.vm["SP_EC"] == 200
    cmd(d, cmd="weather", scenario="storm")
    d.run(20)
    assert json.loads(d.state())["weather"]["look"] == "storm"
    cmd(d, cmd="weather", scenario="clear")
    d.run(20)
    assert json.loads(d.state())["weather"]["look"] == "clear"
    assert cmd(d, cmd="challenge", action="start")["ok"]
    hidden = d.challenge["fault"]
    s = json.loads(d.state())
    assert s["faults"] == [] and s["challenge"]["truth"] is None
    assert not cmd(d, cmd="fault", name="p201_trip", on=True)["ok"], "locked during the challenge"
    cmd(d, cmd="challenge", action="hint")
    assert json.loads(d.state())["challenge"]["field"] is not None
    r = cmd(d, cmd="challenge", action="answer", fault=hidden)["result"]
    assert r["correct"] and hidden not in d.b.plant.faults
    cmd(d, cmd="challenge", action="start")
    r = cmd(d, cmd="challenge", action="quit")["result"]
    assert not r["correct"] and r["answered"] == "(gave up)" and r["title"]


def test_web05_skip_night_rolls_the_day():
    d = Demo("17:30", seed=1)
    d.run(TICKS_PER_MIN)
    assert cmd(d, cmd="skip_night")["ok"]
    s = json.loads(d.state())
    assert s["day"] == 2 and s["clock"].startswith("05:5")
