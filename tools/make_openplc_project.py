"""Build an OpenPLC Editor v4 project folder from plc/greenhouse.st (FAT part B, phase 4).

    python tools/make_openplc_project.py                     # writes openplc/GH1_Greenhouse/
    python tools/make_openplc_project.py --plant-port 5021   # plant simulator on another port

The project is what the Editor would save after importing the program and setting up
Modbus by hand, but generated, so it always matches the tested Structured Text:

    project.json                     task MainTask (T#50ms) running Inst0 : Greenhouse
    pous/function-blocks/FB_*.st     each function block, verbatim
    pous/programs/Greenhouse.st      the program, verbatim (AT addresses included)
    devices/configuration.json       target "OpenPLC Runtime v4"
    devices/remote/PLANT.json        Modbus master: the virtual plant, from plc/plant_io_groups.json
    devices/servers/modbus.json      Modbus server on port 502 for the HMI (%MW0..255 backed)

Check and build it headless with the Editor's CLI:

    openplc-cli inspect image openplc/GH1_Greenhouse --target "OpenPLC Runtime v4"
    openplc-cli compile openplc/GH1_Greenhouse --target "OpenPLC Runtime v4" --clean

Upload with tools/openplc_runtime.ps1 (the runtime login is typed by you, hidden).
Adapted from plc-batch-station (T-101).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plc" / "greenhouse.st"
GROUPS = ROOT / "plc" / "plant_io_groups.json"
OUT = ROOT / "openplc" / "GH1_Greenhouse"

PLANT_TIMEOUT_MS = 500
MODBUS_SERVER_PORT = 502
IEC_BYTE = 100            # the program addresses the plant from %IX100.0 / %IW100 upward
MW_COUNT = 256            # %MW0..139 used (FDS 9); the template's 64 would leave %MW64.. unbacked

POU_RE = re.compile(r"^(FUNCTION_BLOCK|PROGRAM)\s+(\w+)\s*\n(.*?)^END_\1\b", re.S | re.M)
TASK_RE = re.compile(r"TASK\s+(\w+)\s*\(\s*INTERVAL\s*:=\s*(T#\w+)\s*,\s*PRIORITY\s*:=\s*(\d+)\s*\)", re.I)
INST_RE = re.compile(r"PROGRAM\s+(\w+)\s+WITH\s+(\w+)\s*:\s*(\w+)", re.I)
COMMENT_RE = re.compile(r"\(\*.*?\*\)", re.S)

# Function code -> (point type label as the Editor writes it, IEC prefix, bit-addressed)
FC_INFO = {
    "1": ("Digital Input (Coil Status)", "%IX", True),
    "2": ("Digital Input (Discrete Input)", "%IX", True),
    "3": ("Analog Input (Holding Register)", "%IW", False),
    "4": ("Analog Input (Input Register)", "%IW", False),
    "5": ("Digital Output (Single Coil)", "%QX", True),
    "6": ("Analog Output (Single Register)", "%QW", False),
    "15": ("Digital Output (Multiple Coils)", "%QX", True),
    "16": ("Analog Output (Multiple Registers)", "%QW", False),
}


def pou_files(text: str) -> dict[str, str]:
    """One .st file per POU: its own leading comment block, then the POU verbatim."""
    files, prev_end = {}, 0
    for m in POU_RE.finditer(text):
        kind, name = m.group(1), m.group(2)
        comments = COMMENT_RE.findall(text[prev_end:m.start()])
        doc = comments[-1] + "\n" if comments else ""
        folder = "programs" if kind == "PROGRAM" else "function-blocks"
        files[f"pous/{folder}/{name}.st"] = doc + m.group(0) + "\n"
        prev_end = m.end()
    return files


def plant_device(host: str, port: int) -> dict:
    groups, next_addr = [], {}
    for g in json.loads(GROUPS.read_text(encoding="utf8"))["ioGroups"]:
        fc = str(g["functionCode"])
        label, prefix, is_bit = FC_INFO[fc]
        points = []
        for i in range(g["length"]):
            n = next_addr.get(prefix, 0)
            loc = f"{prefix}{IEC_BYTE + n // 8}.{n % 8}" if is_bit else f"{prefix}{IEC_BYTE + n}"
            next_addr[prefix] = n + 1
            points.append({"id": f"{g['name']}_{i}", "name": f"{g['name']}_{i}", "type": label,
                           "iecLocation": loc, "alias": ""})
        groups.append({"id": g["name"], "name": g["name"], "functionCode": fc, "cycleTime": g["cycleTime"],
                       "offset": str(g["offset"]), "length": g["length"],
                       "errorHandling": g["errorHandling"], "ioPoints": points})
    return {"name": "PLANT", "protocol": "modbus-tcp",
            "modbusTcpConfig": {"transport": "tcp", "host": host, "port": port,
                                "timeout": PLANT_TIMEOUT_MS, "slaveId": 1, "ioGroups": groups}}


def build(plant_host: str = "127.0.0.1", plant_port: int = 5020) -> dict[str, str]:
    text = SRC.read_text(encoding="utf8")
    task, inst = TASK_RE.search(text), INST_RE.search(text)
    if not (task and inst):
        raise ValueError("TASK / PROGRAM instance not found in the CONFIGURATION block")
    project = {
        "meta": {"name": "GH1_Greenhouse", "type": "plc-project"},
        "data": {"pous": [], "dataTypes": [], "libraries": [], "configuration": {"resource": {
            "tasks": [{"name": task.group(1), "triggering": "Cyclic", "interval": task.group(2),
                       "priority": int(task.group(3))}],
            "instances": [{"name": inst.group(1), "program": inst.group(3), "task": inst.group(2)}],
            "globalVariables": []}}},
    }
    device_cfg = {
        "deviceBoard": "OpenPLC Runtime v4", "communicationPort": "", "runtimeIpAddress": "127.0.0.1",
        "vendorScreenData": {}, "vendorScreenDataByBoard": {},
        "persistentStorage": {"enabled": False, "path": "", "flushSeconds": 5},
        "persistentStorageByBoard": {}, "selectedPlatformOptions": {}, "vppPackagePinsByBoard": {},
        "targetDevice": {"orchestratorId": "", "deviceId": "", "deviceName": ""},
    }
    # Holding registers are laid out %QW first, then %MW. Pinning %QW to 1024 keeps %MW0 at
    # holding register 1024 (the OpenPLC v3 map the HMI uses). The %MW count sizes the
    # runtime's memory-word table: %MW0..255 = holding registers 1024..1279.
    server = {"name": "modbus", "protocol": "modbus-tcp",
              "modbusSlaveConfig": {"enabled": True, "transports": ["tcp"], "networkInterface": "0.0.0.0",
                                    "port": MODBUS_SERVER_PORT,
                                    "bufferMapping": {"holdingRegisters": {"qwCount": 1024, "mwCount": MW_COUNT}}}}
    dump = lambda o: json.dumps(o, indent=2) + "\n"  # noqa: E731
    files = {"project.json": dump(project), "devices/configuration.json": dump(device_cfg),
             "devices/pin-mapping.json": "{}\n", "devices/remote/PLANT.json": dump(plant_device(plant_host, plant_port)),
             "devices/servers/modbus.json": dump(server)}
    files.update(pou_files(text))
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plant-host", default="127.0.0.1", help="plant simulator, as the runtime sees it")
    ap.add_argument("--plant-port", type=int, default=5020)
    args = ap.parse_args()
    files = build(args.plant_host, args.plant_port)
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, content in files.items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf8", newline="\n")
    pous = sorted(r for r in files if r.startswith("pous/"))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(files)} files ({len(pous)} POUs), "
          f"PLANT at {args.plant_host}:{args.plant_port}")
    for r in sorted(files):
        print("  ", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
