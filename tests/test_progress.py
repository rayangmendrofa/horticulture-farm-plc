"""Browser demo progress layer: coins, levels, building, upgrades, market, problems and repairs, save (PRG)."""
import json

from farmsim.progress import FIX, GROUPS, Farm, meta
from farmsim.webdemo import TICKS_PER_MIN, WEB_FAULTS


def cmd(f, **m):
    return json.loads(f.command(json.dumps(m)))


def ripen(f, house, zone):
    bed = f.houses[house].beds[zone]
    bed.days = bed.target_days


def stock_up(f, n=5):
    f.tools = ["wrench", "multimeter", "ladder"]
    f.parts = {k: n for k in f.parts}


def test_prg01_new_farm_starts_simple():
    f = Farm("10:30", seed=1)
    s = json.loads(f.state())
    h = s["houses"][0]
    assert [z["locked"] for z in h["zones"]] == [False, False, True, True]
    assert h["zones"][0]["crop"] == "kangkung" and s["farm"]["level"] == 1
    assert s["farm"]["crops"] == ["kangkung"] and s["farm"]["crop_locks"]["chili"] == "harvest water spinach first"
    assert s["farm"]["tools"] == ["wrench"] and s["farm"]["parts"]["drippers"] == 1, "starter kit"
    assert not cmd(f, cmd="plant", house=0, zone=2, crop="kangkung")["ok"], "bed 3 is not built"
    assert not cmd(f, cmd="plant", house=0, zone=1, crop="chili")["ok"], "chili comes after a kangkung harvest"
    assert cmd(f, cmd="plant", house=0, zone=1, crop="kangkung")["ok"]
    vm = f.houses[0].b.vm
    assert vm["SP_ZONE_EN"] == 0b11
    assert (vm["SP_COOL_T"], vm["SP_SCREEN_RAD"], vm["SP_RAD_SUM"]) == (400, 1000, 300), "hardware not installed"
    assert not cmd(f, cmd="setpoint", house=0, name="SP_COOL_T", value=30)["ok"]
    assert sorted(GROUPS["water"] + GROUPS["beds"] + GROUPS["feed"] + GROUPS["climate"]) == sorted(WEB_FAULTS)
    assert sorted(FIX) == sorted(WEB_FAULTS), "every fault has a repair"
    m = json.loads(meta())
    assert len(m["achievements"]) == 20 and len(m["upgrades"]) == 7 and len(m["cosmetics"]) == 14


def test_prg02_harvest_pays_and_unlocks():
    f = Farm("10:30", seed=1)
    ripen(f, 0, 0)
    r = cmd(f, cmd="harvest", house=0, zone=0)
    assert r["kg"] > 0 and r["coins"] == round(r["kg"] * 0.6)
    s = json.loads(f.state())["farm"]
    assert s["harvests"] == 1 and "first_harvest" in s["ach"]
    assert {"type": "unlock", "crops": ["chili"]} in s["events"], "the first harvest opens the next crop"
    assert json.loads(f.state())["farm"]["events"] == [], "events are sent once"
    f.xp = 1199
    cmd(f, cmd="plant", house=0, zone=0, crop="kangkung")
    ripen(f, 0, 0)
    cmd(f, cmd="harvest", house=0, zone=0)
    ev = json.loads(f.state())["farm"]["events"]
    assert {"type": "level", "level": 2} in ev


def test_prg03_builds_need_parts_and_a_roadblock_needs_a_repair():
    f = Farm("10:30", seed=1)
    assert not cmd(f, cmd="build", item="bed:0:2")["ok"], "no coins yet"
    f.coins = 5000
    assert cmd(f, cmd="build", item="bed:0:2")["built"] == "bed:0:2" and f.coins == 4200
    assert f.parts["drippers"] == 0, "the bed used the dripper kit"
    f.xp = 1500
    r = cmd(f, cmd="build", item="bed:0:3")
    assert not r["ok"] and "Dripper kit" in r["error"]
    assert cmd(f, cmd="buy", item="drippers")["ok"] and f.coins == 4120
    r = cmd(f, cmd="build", item="bed:0:3")
    assert r["roadblock"] and f.houses[0].challenge["fault"] == "p201_trip" and f.open_beds[0] == 3
    f.run(40)
    assert json.loads(f.state())["houses"][0]["field"]["pump_trip"], "the problem shows in the field"
    cmd(f, cmd="challenge", action="answer", fault="z3_clogged")         # wrong: fixed for you, no build
    assert f.trouble is None and not f.repairs and f.open_beds[0] == 3
    assert "p201_trip" not in f.houses[0].b.plant.faults
    cmd(f, cmd="build", item="bed:0:3")
    r = cmd(f, cmd="challenge", action="answer", fault="p201_trip")
    assert r["result"]["correct"] and f.open_beds[0] == 3, "found, but not repaired yet"
    assert "p201_trip" in f.houses[0].b.plant.faults and f.repairs[0]["fault"] == "p201_trip"
    r = cmd(f, cmd="repair", house=0, fault="p201_trip")
    assert not r["ok"] and "Multimeter" in r["error"]
    cmd(f, cmd="buy", item="multimeter")
    coins = f.coins
    assert cmd(f, cmd="repair", house=0, fault="p201_trip")["ok"]
    assert f.open_beds[0] == 4 and "p201_trip" not in f.houses[0].b.plant.faults and f.parts["drippers"] == 0
    assert f.coins == coins - 2000 + 2 * 100, "built on repair, plus handy and full house"
    assert {"detective", "sharp_eye", "handy", "full_house"} <= set(f.ach)


def test_prg04_second_greenhouse_runs_the_same_program():
    f = Farm("10:30", seed=1)
    f.coins, f.xp, f.cleared = 10000, 5000, ["house:1"]
    assert "Ladder" in cmd(f, cmd="build", item="house:1")["error"]
    stock_up(f)
    assert cmd(f, cmd="build", item="house:1")["built"] == "house:1"
    assert len(f.houses) == 2 and "scale_out" in f.ach
    assert f.houses[1].b.vm is not f.houses[0].b.vm and f.houses[1].park == f.houses[0].park
    cmd(f, cmd="plant", house=1, zone=0, crop="kangkung")
    f.run(40)
    s = json.loads(f.state())
    assert s["houses"][1]["zones"][0]["crop"] == "kangkung" and s["houses"][0]["zones"][0]["crop"] == "kangkung"
    assert f.houses[0].ticks == f.houses[1].ticks
    cmd(f, cmd="weather", scenario="storm")
    assert all(h.b.plant.weather.scenario == "cloudy" for h in f.houses)


def test_prg05_upgrades_unpark_the_plc_functions():
    f = Farm("10:30", seed=1)
    f.coins, f.xp = 20000, 5000
    assert "Ladder" in cmd(f, cmd="build", item="up:net")["error"]
    stock_up(f, 1)
    for u in ("solar", "net", "film", "cool"):
        assert cmd(f, cmd="build", item="up:" + u)["built"] == "up:" + u
    assert f.parts["cable"] == 0 and f.parts["pipe_kit"] == 0
    vm = f.houses[0].b.vm
    assert vm["SP_RAD_SUM"] == 130 and vm["SP_SCREEN_RAD"] == 650 and vm["SP_COOL_T"] == 340
    assert f.houses[0].park == {"SP_VPD_FOG": 2.5} and f.houses[0].b.plant.cfg.transmissivity == 0.75
    assert cmd(f, cmd="setpoint", house=0, name="SP_COOL_T", value=31)["ok"] and "tuner" in f.ach


def test_prg06_items_and_robot():
    f = Farm("10:30", seed=1)
    assert not cmd(f, cmd="use", item="tea")["ok"]
    f.coins = 5000
    f.houses[0].beds[0].health = 50
    cmd(f, cmd="buy", item="tea")
    cmd(f, cmd="use", item="tea")
    assert f.houses[0].beds[0].health == 80 and f.items["tea"] == 0
    cmd(f, cmd="buy", item="lamp")
    cmd(f, cmd="use", item="lamp")
    f.run(20)
    assert f.houses[0].light_floor == 0.6 and json.loads(f.state())["farm"]["boosts"]["lamp"] > 300
    cmd(f, cmd="buy", item="market")
    cmd(f, cmd="use", item="market")
    f.upgrades.append("robot")
    ripen(f, 0, 0)
    f.run(TICKS_PER_MIN)
    ev = [e for e in json.loads(f.state())["farm"]["events"] if e["type"] == "auto_harvest"]
    assert ev and ev[0]["coins"] == round(ev[0]["kg"] * 0.6 * 1.5) and f.houses[0].beds[0].crop is None


def test_prg07_problems_are_found_then_repaired():
    f = Farm("10:59", seed=4)
    f.harvests = 1
    f.rng.random = lambda: 0.0                           # a problem every hour
    f.run(2 * TICKS_PER_MIN)
    tr = f.trouble
    assert tr and tr["kind"] == "problem"
    hi, fault = tr["house"], f.houses[tr["house"]].challenge["fault"]
    r = cmd(f, cmd="challenge", action="answer", fault=fault)
    assert r["result"]["correct"] and f.trouble is None and fault in f.houses[hi].b.plant.faults
    f.houses[0].b.plant.set_clock("11:59")
    f.run(2 * TICKS_PER_MIN)
    assert f.trouble is None, "no new problem while a repair is waiting"
    stock_up(f)
    coins = f.coins
    assert cmd(f, cmd="repair", house=hi, fault=fault)["ok"]
    assert f.coins == coins + 150 + 100 and fault not in f.houses[hi].b.plant.faults and not f.repairs
    f.start_trouble(0, "burst_pipe", "problem")
    cmd(f, cmd="challenge", action="answer", fault="burst_pipe")
    f.coins = 300
    assert cmd(f, cmd="repair", house=0, fault="burst_pipe", hire=True)["ok"] and f.coins == 50
    f.start_trouble(0, "acid_empty", "problem")
    f.coins = 50
    cmd(f, cmd="challenge", action="answer", fault="p201_trip")
    assert f.coins == 0 and "acid_empty" not in f.houses[0].b.plant.faults, "a wrong guess: the technician fixes it"
    cmd(f, cmd="problems", on=False)
    f.houses[0].b.plant.set_clock("12:59")
    f.run(2 * TICKS_PER_MIN)
    assert f.trouble is None


def test_prg08_cosmetics():
    f = Farm("10:30", seed=1)
    assert not cmd(f, cmd="cosmetic", id="paint:red")["ok"]
    f.coins = 1000
    assert cmd(f, cmd="cosmetic", id="paint:red")["ok"] and f.style["paint"] == "red"
    assert "stylish" in f.ach and f.coins == 1000 - 500 + 100
    cmd(f, cmd="cosmetic", id="paint:white")
    cmd(f, cmd="cosmetic", id="paint:red")
    assert f.style["paint"] == "red" and f.coins == 600, "owned: wearing it again is free"
    cmd(f, cmd="cosmetic", id="decor:flag")
    cmd(f, cmd="cosmetic", id="decor:flag")
    assert f.style["decor"] == [] and "decor:flag" in f.owned


def test_prg09_save_and_load():
    f = Farm("10:30", seed=1)
    f.coins, f.xp, f.ach, f.upgrades, f.items["bees"] = 1234, 2000, ["tuner"], ["net"], 2
    f.tools, f.parts["cable"] = ["wrench", "ladder"], 3
    f.owned.append("outfit:pajama")
    f.style["outfit"] = "pajama"
    cmd(f, cmd="plant", house=0, zone=1, crop="kangkung")
    f.houses[0].beds[1].days, f.houses[0].beds[1].health = 7.5, 80
    f.start_trouble(0, "z4_leak", "problem")
    cmd(f, cmd="challenge", action="answer", fault="z4_leak")
    g = Farm(save=json.loads(f.save()))
    assert (g.coins, g.level, g.ach[0], g.open_beds, g.upgrades, g.items["bees"]) == (1434, 2, "tuner", [2], ["net"], 2)
    assert g.tools == ["wrench", "ladder"] and g.parts["cable"] == 3 and g.style["outfit"] == "pajama"
    assert g.repairs[0]["fault"] == "z4_leak" and "z4_leak" in g.houses[0].b.plant.faults, "still broken"
    b = g.houses[0].beds[1]
    assert (b.crop, b.days, b.health) == ("kangkung", 7.5, 80)
    assert g.houses[0].b.vm["SP_ZONE_EN"] == 0b11 and g.houses[0].b.vm["SP_SCREEN_RAD"] == 650


def test_prg10_crop_tree_and_upgrade_tree():
    f = Farm("10:30", seed=1)
    f.coins, f.xp, f.crops_done = 50000, 25000, ["kangkung", "chili"]
    f._check_unlocks()
    f.state()                                            # send the events so far
    assert f.crops_open() == ["kangkung", "chili", "tomato"], "level alone is not enough"
    assert f.crop_lock("cucumber") == "needs light-sum watering" and f.crop_lock("melon") == "harvest cucumber first"
    stock_up(f)
    r = cmd(f, cmd="build", item="up:fog")
    assert not r["ok"] and "Pad-and-fan cooling" in r["error"], "fogging comes after cooling"
    assert not cmd(f, cmd="build", item="up:cool")["ok"], "cooling comes after the shade net"
    for u in ("net", "cool", "solar", "fog"):
        assert cmd(f, cmd="build", item="up:" + u)["ok"], u
    ev = [e for e in json.loads(f.state())["farm"]["events"] if e["type"] == "unlock"]
    assert [c for e in ev for c in e["crops"]] == ["lettuce", "cucumber"]
    assert f.crop_lock("strawberry") == "harvest lettuce first"
    m = json.loads(meta())
    assert {n["id"] for n in m["up_tree"]} == {u for u in ("multimeter", "ladder", "wrench")} | {u["id"] for u in m["upgrades"]}
    assert all(n["after"] in [c["id"] for c in m["crop_tree"]] for n in m["crop_tree"] if n["after"])


def test_prg11_dynamic_days_market_orders_pests_and_birds():
    f = Farm("17:30", seed=2)
    f.harvests, f.coins = 1, 1000
    f.rng.random = lambda: 0.0                           # every chance comes up
    cmd(f, cmd="skip_night")
    f.run(20)                                            # the farm notices the new day
    ev = [e for e in json.loads(f.state())["farm"]["events"] if e["type"] == "new_day"][0]
    assert ev["weather"] == "clear" and ev["heat"] and f.houses[0].b.plant.weather.heat == 4.0, "a heatwave"
    assert ev["hot"] == "kangkung" and f.price_mult("kangkung") == 1.8
    o = f.order
    assert o and o["crop"] == "kangkung" and o["kg"] >= 600 and o["due"] == f._day + 3
    f.houses[0].b.plant.set_clock("10:59")
    ripen(f, 0, 0)
    cmd(f, cmd="plant", house=0, zone=1, crop="kangkung")
    f.run(2 * TICKS_PER_MIN)
    ev = json.loads(f.state())["farm"]["events"]
    assert any(e["type"] == "pest" for e in ev) and f.houses[0].beds[1].pest, "pests on the growing bed"
    assert not cmd(f, cmd="spray", house=0, zone=1)["ok"], "needs neem oil"
    cmd(f, cmd="buy", item="neem")
    assert cmd(f, cmd="spray", house=0, zone=1)["ok"] and not f.houses[0].beds[1].pest and "pest_control" in f.ach
    o["kg"], coins, n_ach = 100, f.coins, len(f.ach)
    r = cmd(f, cmd="harvest", house=0, zone=0)
    assert f.order is None and "trader" in f.ach
    assert f.coins == coins + r["coins"] + o["bonus"] + 100 * (len(f.ach) - n_ach), "harvest, bonus and awards"
    f.houses[0].beds[0].plant("tomato")
    ripen(f, 0, 0)
    f.houses[0].b.plant.set_clock("11:59")
    f.run(2 * TICKS_PER_MIN)
    assert f.houses[0].beds[0].health == 85, "birds pecked the ripe tomatoes"
    f.style["decor"].append("decor:scarecrow")
    f.houses[0].b.plant.set_clock("12:59")
    f.run(2 * TICKS_PER_MIN)
    assert f.houses[0].beds[0].health == 85, "the scarecrow keeps them off"
