"""The generated OpenPLC Editor project matches the program (FAT part B setup, phase 4)."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_openplc_project as mk  # noqa: E402

from farmsim import tags  # noqa: E402

ST = (ROOT / "plc" / "greenhouse.st").read_text(encoding="utf-8")
LOCATED = set(re.findall(r"AT\s+(%[IQM][XW][\d.]+)", ST))


def test_project_files_and_task():
    files = mk.build(plant_port=5021)
    assert sorted(f for f in files if f.startswith("pous/")) == [
        "pous/function-blocks/FB_Actuator.st", "pous/function-blocks/FB_AnalogIn.st",
        "pous/function-blocks/FB_Motor.st", "pous/function-blocks/FB_PIControl.st",
        "pous/function-blocks/FB_Valve.st", "pous/programs/Greenhouse.st"]
    res = json.loads(files["project.json"])["data"]["configuration"]["resource"]
    assert res["tasks"][0]["interval"] == "T#50ms"
    assert res["instances"] == [{"name": "Inst0", "program": "Greenhouse", "task": "MainTask"}]
    assert "END_PROGRAM" in files["pous/programs/Greenhouse.st"]


def test_plant_device_covers_every_field_address():
    """Every %IX/%IW/%QX/%QW in the program has a PLANT point, in the plant server's order."""
    dev = json.loads(mk.build(plant_port=5021)["devices/remote/PLANT.json"])["modbusTcpConfig"]
    assert dev["port"] == 5021
    points = {p["iecLocation"]: g for g in dev["ioGroups"] for p in g["ioPoints"]}
    field = {a for a in LOCATED if a[1] in "IQ"}
    assert field <= set(points), sorted(field - set(points))
    assert points["%IX100.0"]["name"] == "PLANT_DI" and points["%IX103.0"]["name"] == "PLANT_DI"
    assert points["%IW115"]["name"] == "PLANT_AI" and points["%QX102.5"]["name"] == "PLANT_DO"
    assert points["%QW102"]["name"] == "PLANT_AO"
    safe = {g["name"]: g["errorHandling"] for g in dev["ioGroups"]}
    assert safe["PLANT_DI"] == safe["PLANT_AI"] == "set-to-zero", "comms loss must read as E-stop (FDS 13)"


def test_modbus_server_backs_the_hmi_map():
    srv = json.loads(mk.build()["devices/servers/modbus.json"])["modbusSlaveConfig"]
    hr = srv["bufferMapping"]["holdingRegisters"]
    assert srv["port"] == 502 and hr["qwCount"] == 1024          # %MW0 = holding register 1024
    top = max(int(a[3:]) for a in LOCATED if a.startswith("%MW"))
    assert top == tags.STATUS_START + len(tags.STATUS_FIELDS) - 1 == 139
    assert hr["mwCount"] > top
