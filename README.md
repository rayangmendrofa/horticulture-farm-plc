# GH-1 Tropical Greenhouse — PLC control system

A PLC project for a 1 000 m² tropical lowland greenhouse: **drip irrigation** in four zones, **fertigation** (inline A/B nutrient and acid dosing on EC and pH) and **climate control** (roof vents, shade net, fogging, pad-and-fan cooling with weather overrides). The program is **IEC 61131-3 Structured Text** for **OpenPLC v4**, integrated over **Modbus TCP**. A virtual plant (weather, greenhouse air, crop, hydraulics, water chemistry) replaces the hardware, so the whole system runs and is tested on a laptop.

> **Status — phase 2 of 5 done.** PLC program, plant model, soft-PLC with fast-forward, and the automated FAT are in place and passing; the program compiles clean with STruC++ (the OpenPLC v4 compiler). The web HMI (phase 3) and the run on OpenPLC Runtime v4 (phase 4) are next. See [docs/SCOPE.md](docs/SCOPE.md).

## What it does
- **Irrigation**: cycles start on accumulated solar radiation or on a maximum interval, inside a day window. Each cycle pre-mixes the nutrient solution through a return loop until EC and pH are in band, then waters the zones one by one, metered by a flow transmitter, with open-before-close changeover.
- **Fertigation**: ratio control with feedback trim — dosing proportional to the measured water flow, corrected by PI loops with an integration zone. Duplicated pH probes with validation and fallback.
- **Climate**: a state machine (VENT → COOL-START → PRE-WET → COOL → PAD-DRY). Vents follow the larger of a temperature and a humidity demand, limited by rain, wind and storm. Pad-and-fan only with the vents closed.
- **Protection**: E-stop, pump dry-run, dead-head and pressure limits, crop-protection limits on EC and pH, actuator travel supervision, motor feedback lock-outs, NAMUR NE 43 signal faults — each with a defined fallback.

## Run the tests
Requires Python 3.10+.
```bash
pip install -e ".[dev]"
pytest -v                       # automated FAT, about 3 min
pytest -v --runslow             # plus one full simulated day, about 10 min more
FARMSIM_STRICT=1 pytest -v      # same FAT on the strict VM (run-time IEC type checks)
python tools/check_openplc_compile.py   # STruC++ compile check (FAT OPL-01)
python tools/simulate_day.py    # hourly summary of a simulated day
```

## Run it
```bash
python -m farmsim fast --speed 20      # PLC + plant in virtual time, 20x (a day in 72 min)
python -m farmsim live                 # plant + soft-PLC over Modbus TCP, real time
```
The PLC's Modbus server (port 5502) exposes the HMI registers `%MW0–139` (holding registers 1024–1163); see [FDS §9](docs/FDS.md#9-hmi-interface).

## Documentation
| Document | For |
|---|---|
| [Scope](docs/SCOPE.md) | What was agreed, and what is out of scope |
| [PRD](docs/PRD.md) | Requirements, each traced to an automated test |
| [FDS](docs/FDS.md) | I/O list, sequences, control loops, cause & effect, alarms, register map |
| [Credits](CREDITS.md) | Software, standards and references this project builds on |
