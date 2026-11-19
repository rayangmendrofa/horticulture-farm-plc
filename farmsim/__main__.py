"""Command line entry point.

    python -m farmsim live       plant + soft-PLC in one process (separate TCP links), real time
    python -m farmsim fast       fast-forward: PLC and plant in virtual time, --speed x real time
    python -m farmsim plant      virtual plant only (Modbus remote I/O, :5020)
    python -m farmsim softplc    soft-PLC only (Modbus server :5502, polls the plant)

The web HMI is added in phase 3.
"""
from __future__ import annotations

import sys
import time


def _common(ap):
    ap.add_argument("--clock", default="06:00", help="start time of day, HH:MM")
    ap.add_argument("--scenario", default="clear", choices=("clear", "cloudy", "rain", "storm"))
    ap.add_argument("--plc-port", type=int, default=5502)
    ap.add_argument("--plant-port", type=int, default=5020)


def live(argv):
    import argparse

    from .plant import Plant
    from .plant_server import PlantServer
    from .softplc import SlaveDevice, SoftPLC

    ap = argparse.ArgumentParser(prog="farmsim live")
    _common(ap)
    a = ap.parse_args(argv)
    plant = PlantServer("127.0.0.1", a.plant_port, Plant(clock=a.clock, scenario=a.scenario)).start()
    plc = SoftPLC(listen=("127.0.0.1", a.plc_port), device=SlaveDevice("127.0.0.1", plant.port)).start()
    print(f"GH-1 live: plant 127.0.0.1:{plant.port}, soft-PLC 127.0.0.1:{plc.port} (1x)")
    _wait(plc, plant)


def fast(argv):
    import argparse

    from .plant import Plant
    from .plant_server import PlantServer
    from .softplc import FastPLC

    ap = argparse.ArgumentParser(prog="farmsim fast")
    _common(ap)
    ap.add_argument("--speed", type=int, default=20, help="scans per 50 ms task (x real time)")
    a = ap.parse_args(argv)
    plant = PlantServer("127.0.0.1", a.plant_port, Plant(clock=a.clock, scenario=a.scenario),
                        passive=True).start()
    plc = FastPLC(plant, listen=("127.0.0.1", a.plc_port), speed=a.speed).start()
    print(f"GH-1 fast-forward x{a.speed}: soft-PLC 127.0.0.1:{plc.port}, "
          f"plant simulation registers 127.0.0.1:{plant.port}")
    _wait(plc, plant)


def _wait(*parts):
    print("Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in parts:
            p.stop()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd, rest = (argv[0], argv[1:]) if argv else ("fast", [])
    if cmd == "live":
        return live(rest)
    if cmd == "fast":
        return fast(rest)
    if cmd == "plant":
        from .plant_server import main as m
    elif cmd == "softplc":
        from .softplc import main as m
    else:
        print(__doc__)
        return 2
    return m(rest)


if __name__ == "__main__":
    sys.exit(main())
