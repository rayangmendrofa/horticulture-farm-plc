"""Command line entry point.

    python -m farmsim fast       fast-forward: PLC and plant in virtual time + web HMI (default)
    python -m farmsim live       plant + soft-PLC over separate TCP links, real time + web HMI
    python -m farmsim plant      virtual plant only (Modbus remote I/O, :5020)
    python -m farmsim softplc    soft-PLC only (Modbus server :5502, polls the plant)
    python -m farmsim hmi        web HMI only (--plc <ip>:502 for the OpenPLC runtime)

fast and live serve the HMI on http://127.0.0.1:8080 (--http to change, --no-hmi to skip).
"""
from __future__ import annotations

import sys
import time


def _common(ap):
    ap.add_argument("--clock", default="06:00", help="start time of day, HH:MM")
    ap.add_argument("--scenario", default="clear", choices=("clear", "cloudy", "rain", "storm"))
    ap.add_argument("--plc-port", type=int, default=5502)
    ap.add_argument("--plant-port", type=int, default=5020)
    ap.add_argument("--http", default="127.0.0.1:8080", help="web HMI address")
    ap.add_argument("--no-hmi", action="store_true", help="do not start the web HMI")
    ap.add_argument("--no-browser", action="store_true", help="do not open the HMI in a browser")


def _hmi(a, plc, plant):
    if a.no_hmi:
        return []
    from .hmi import HMIBackend, HMIServer, hostport
    host, port = hostport(a.http, 8080)
    srv = HMIServer(HMIBackend(("127.0.0.1", plc.port), ("127.0.0.1", plant.port)), host, port).start()
    url = f"http://{host}:{srv.port}"
    print(f"web HMI: {url}")
    if not a.no_browser:
        import webbrowser
        webbrowser.open(url)
    return [srv]


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
    _wait(*_hmi(a, plc, plant), plc, plant)


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
    _wait(*_hmi(a, plc, plant), plc, plant)


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
    elif cmd == "hmi":
        from .hmi import main as m
    else:
        print(__doc__)
        return 2
    return m(rest)


if __name__ == "__main__":
    sys.exit(main())
