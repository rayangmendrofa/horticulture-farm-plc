"""Generate docs/TROUBLESHOOTING.md from the fault knowledge base (farmsim/faults.py).

    python tools/gen_troubleshooting.py

Adapted from plc-batch-station (T-101).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from farmsim import tags  # noqa: E402
from farmsim.faults import FAULT_INFO  # noqa: E402

OUT = ROOT / "docs" / "TROUBLESHOOTING.md"
LEVEL = {1: "an alarm points to it", 2: "an alarm, but the cause needs reasoning",
         3: "no alarm: trends and a field check find it"}
CLASS = {"trip": "trip", "lockout": "lock-out", "alarm": "alarm", "warning": "warning"}


def anchor(title: str) -> str:
    """GitHub heading anchor."""
    a = re.sub(r"[^\w\- ]", "", title.lower()).strip().replace(" ", "-")
    return "#" + a


def link(key: str) -> str:
    t = FAULT_INFO[key]["title"]
    return f"[{t}]({anchor(t)})"


HEAD = """# Troubleshooting and maintenance guide — GH-1

> Generated from `farmsim/faults.py` by `tools/gen_troubleshooting.py`. Edit the knowledge base, not this file.
> The same entries drive the **troubleshooting challenge** in the HMI's field-simulation panel.

## 1. Before you touch anything
- **Isolate and lock out** (LOTO): the main switch -Q0, or the device's own breaker, before working on power circuits. Prove dead with a tester you have just proven on a live source.
- **The PLC is not a safety device.** A welded contactor, a passing valve or a drifted sensor can defeat it. "The PLC output is off" is never isolation.
- **Acid and concentrates**: the fertigation skid holds 10 % nitric acid and strong fertiliser. Goggles, gloves and the eyewash first.
- **Record** what you find and what you change. Every fault is a chance to improve the design.

## 2. Method
1. **Read the symptom exactly.** Which step, which alarm, what the operator did, since when. The HMI's *Alarms* page keeps a cleared alarm in the list until RESET, so the first alarm is usually still visible.
2. **Compare what the PLC sees with what is really there.** The *Devices & I/O* page tells you *why* a device is held off (its interlock reasons) and shows every input and output like the module LEDs. Then go to the field: local gauge, sight tube, a bucket test, a hand-held meter, a clamp meter.
3. **Use the trends.** Most subtle faults show as a change from normal: a zone that waters longer than the others, dosing higher than last week, a house warmer than the HMI says. Know what normal looks like (commissioning baseline).
4. **Half-split the signal path.** Field device → cable → terminal → I/O module channel → PLC tag. Measure in the middle, move towards the fault.
5. **Fix the cause, not the symptom.** Resetting a breaker or an alarm without knowing why is how equipment gets damaged.
6. **Test after repair.** Re-run the relevant line of the [I/O checkout sheet](IO_CHECKOUT.md) or the FAT test.

## 3. Symptom index
| Symptom | Look at |
|---|---|
| Irrigation tripped (FAULT, step 99) | the first trip alarm in the list; §4 |
| Zones get less water than counted, no alarm | {xv301}, {ft201h} |
| One zone waters longer than the others, no alarm | {z2} |
| Dosing runs higher than usual, no alarm | {stock_a}, {xv301} |
| Crop grows slowly, EC on the HMI is perfect | {ech} |
| House hot, pad-and-fan never starts | {ttl}, ST-101 fault (storm assumed, {st101}) |
| Vents stay nearly closed on a dry day | {rain} |
| pH probes disagree (A09) | {phd} |
| A motor locks out (A04, A14–A16, A38–A45) | the device's breaker (-Q…/-F…), §5 |
| Out of band, then HOLD and A10 | empty stock or acid tank, a dosing pump, the analysers |

## 4. Alarm reference
| Tag | Alarm | Class | First checks |
|---|---|---|---|
"""

ALARM_CHECKS = {
    0: "E-stop stations, safety relay -K0 LEDs, safety circuit wiring",
    1: "HMI clock vs real time; coupler clock/NTP",
    2: "T-201 sight tube; refill (XV-201, A03); LSL-201 switch",
    3: "XV-201 coil voltage, valve, supply pressure, strainer",
    4: "-Q201 tripped? -K201 picking up? feedback contact wiring",
    5: "Strainer, manual valves, zone valves opening",
    6: "Walk the main line: burst, open drain valve; pump primed?",
    7: "Hand-held EC at a dripper; stock strength; AIT-301 calibration",
    8: "Hand-held pH at a dripper; acid pump stuck on; analyser calibration",
    9: "Hand-held pH of a sample: which probe is wrong?",
    10: "Stock and acid levels, dosing pumps, analysers; why EC/pH cannot reach band",
    11: "Stock tank A level, LSL-311",
    12: "Stock tank B level, LSL-312",
    13: "Acid tank level, LSL-313 (PPE)",
    14: "-F311, pump fault LED, suction",
    15: "-F312, pump fault LED, suction",
    16: "-F313, pump fault LED",
    17: "Walk the zone: leak, lateral off, broken dripper",
    18: "Bucket test; precipitate or biofilm; zone valve fully open?",
    19: "Zone flow very low or zero: valve, clogging, pressure",
    20: "Loop current LT-201 (0 mA = open loop)",
    21: "Loop current FT-201; flowmeter display",
    22: "Loop current PT-201; local gauge",
    23: "Loop current AIT-301; analyser power",
    24: "Loop current AIT-302; probe cable",
    25: "Loop current AIT-303; probe cable",
    26: "Both pH analysers: power, cables, probes",
    27: "Loop current FT-402; drain gutter sensor",
    28: "Shot size vs crop demand; FT-402 and FT-201 readings",
    29: "Loop current RT-101; pyranometer dome",
    30: "Loop current ST-101; anemometer turning",
    31: "Loop currents TT-101 / MT-101; weather-station cable",
    32: "Loop current TT-501; aspirated sensor box",
    33: "Loop current MT-501",
    34: "Loop current AT-502; analyser",
    35: "Loop current ZT-511; position transmitter",
    36: "Vent drive: jammed, coupling, gear; motor turning?",
    37: "Net drive: snagged fabric, pull wire",
    38: "-Q511 tripped; drive free?",
    39: "-Q521 tripped; net free?",
    40: "-Q601, belt, bearings",
    41: "-Q602, belt, bearings",
    42: "-Q603, belt, bearings",
    43: "-Q531; sump level; impeller",
    44: "Float valve, clean-water supply, sump leak",
    45: "-Q541; inlet pressure and fine filter",
    46: "Vents, net, fans working? Set points sensible?",
    47: "Cooling capacity, failed fans or pads; crop damage risk",
    48: "Vents wide open with a dense crop; AT-502 calibration",
}
assert set(ALARM_CHECKS) == {n for n, _t, _c in tags.ALARMS}

PM = """
## 6. Preventive maintenance
The PLC counts starts and running minutes of P-201, the fans and the pad and fog pumps, zone-valve cycles, vent reversals and net strokes (*Devices & I/O* page, `%MW122–139`). Use them to plan maintenance by use, not by calendar alone.

| Item | Interval (suggested) | Task | Catches |
|---|---|---|---|
| AIT-301 EC | weekly | Hand-held EC at a dripper vs AIT-301; clean the cell, calibrate monthly | Drift ({ech}) |
| AIT-302/303 pH | 2 weeks | Two-point calibration (pH 4 and 7), one probe at a time so the other keeps control | Drift, ageing glass ({phd}) |
| FT-201 | 6 months | Timed volume on one zone (bucket test) | Flow calibration ({ft201h}) |
| TT-501, MT-501 | 3 months | Compare with a reference thermo-hygrometer in the aspirated box; check the box fan | Drift ({ttl}) |
| Zones Z1–Z4 | monthly | Zone flow vs reference on the Irrigation page; bucket-test 5 drippers per zone; acid flush when flow drops 10 % | Clogging ({z2}) |
| Stock tanks A, B | every new batch | Diluted EC of each concentrate; A and B must match | Mixing errors ({stock_a}) |
| XV-301, zone valves | every 20 000 cycles or yearly | Seat leak test: return line quiet with the valve closed | Passing valves ({xv301}) |
| Strainer before the header | weekly in summer | Clean; note the pressure before/after | Blocked line (A05) |
| P-201, fans F-601…603 | yearly or per run hours | Insulation resistance (≥ 1 MΩ at 500 V DC), current per phase, bearings, fan belts | Trips, worn belts |
| Vent and net drives | 6 months | Stroke test, gearbox oil, limit-switch setting, reversal count vs last time | Travel faults (A36/A37) |
| Pads, pad sump | monthly in summer | Scale and algae, even wetting, float valve | Poor cooling, A44 |
| Fog pump P-541 | 500 h | Oil, seals, fine filter, nozzles | A45, dripping nozzles |
| E-stop circuit | 6 months | Functional test of every E-stop and the safety relay reset | Safety function failure |
"""


def fill(text: str) -> str:
    return text.format(xv301=link("xv301_passing"), ft201h=link("ft201_reads_high"), z2=link("z2_partly_clogged"),
                       stock_a=link("stock_a_weak"), ech=link("ec_reads_high"), ttl=link("tt501_reads_low"),
                       st101=link("st101_break"), rain=link("rain_wire_break"), phd=link("ph_b_drift"))


def render() -> str:
    out = [fill(HEAD)]
    for n, text, cls in tags.ALARMS:
        out.append(f"| A{n:02d} | {text} | {CLASS[cls]} | {ALARM_CHECKS[n]} |\n")
    out.append("\n## 5. Fault reference\nOrdered by how hard they are to find.\n")
    for level in (1, 2, 3):
        for key, f in FAULT_INFO.items():
            if f["level"] != level:
                continue
            out.append(f"\n### {f['title']}\n")
            out.append(f"*Difficulty {level}: {LEVEL[level]}. Simulator fault id: `{key}`.*\n\n")
            out.append(f"| | |\n|---|---|\n| **Symptoms** | {f['symptoms']} |\n| **Confirm** | {f['checks']} |\n"
                       f"| **Root cause** | {f['cause']} |\n| **Fix** | {f['fix']} |\n")
    out.append(fill(PM))
    return "".join(out)


def main() -> int:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(FAULT_INFO)} faults, {len(tags.ALARMS)} alarms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
