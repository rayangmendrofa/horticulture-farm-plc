# Commissioning procedure — GH-1 Tropical Greenhouse

| | |
|---|---|
| **Document** | COM-GH1, revision A |
| **Uses** | [Electrical drawings](drawings/README.md) · [I/O checkout sheet](IO_CHECKOUT.md) · [FDS](FDS.md) · [PRD](PRD.md) (test IDs) · [OpenPLC deployment](openplc.md) · [Troubleshooting](TROUBLESHOOTING.md) |
| **Outcome** | Signed Site Acceptance Test (SAT), tuned set points and the handover package |

Commissioning takes the greenhouse from "installed" to "proven safe and working" in a fixed order. Each phase is complete and signed before the next one starts. **Never energise a circuit that has not passed the checks of the phase before it.** Use the automated FAT (`pytest`) and FAT part B ([openplc.md](openplc.md)) as the reference for what "working" looks like: on site you are proving the *real* plant behaves like the simulated one.

## Roles
| Role | Responsibility |
|---|---|
| Commissioning lead | Owns this procedure, signs each phase |
| Electrical technician | Dead and live tests, I/O checkout |
| Irrigation / fertigation technician | Hydraulics, dosing pumps, stock solutions, calibrations |
| Grower (client) | Crop set points, witnesses interlock tests and the SAT |

## Instruments
Multimeter (CAT III 600 V), insulation resistance tester (500 V DC), earth-continuity tester, RCD tester, 4–20 mA loop calibrator, clamp meter, phase-rotation meter, calibrated hand-held EC and pH meters with buffer solutions (pH 4, 7) and EC standard (1.413 mS/cm), reference thermo-hygrometer, 10 L measuring bucket and stopwatch, laptop with the HMI and OpenPLC Editor. Acid PPE (goggles, gloves, apron) and eyewash for every step that touches the fertigation skid.

---

## Phase 1 — Mechanical completion and dead checks (power OFF, locked out)
| # | Check | Acceptance | ☐ |
|---|---|---|---|
| 1.1 | Panel matches drawing E-12 and the parts list E-13: devices, labels, designations | No discrepancies, or red-lined on the drawings | ☐ |
| 1.2 | Torque check of the power terminals -X1, -X4 and the main switch -Q0 | Torqued and marked | ☐ |
| 1.3 | PE continuity: panel, door, motor frames, pump skid, fan frames, **greenhouse steel structure** bonding | ≤ 0.1 Ω per path (IEC 60204-1 §18.2) | ☐ |
| 1.4 | Insulation resistance of every motor and its cable at 500 V DC, drives disconnected | ≥ 1 MΩ (record values: they are the baseline) | ☐ |
| 1.5 | Motor-protection breakers set to nameplate current (E-02…E-04): -Q201 1.9 A, -Q531 1.0 A, -Q541 4.8 A, -Q601…603 2.6 A, -Q511/-Q521 1.1 A | Settings recorded | ☐ |
| 1.6 | Every field cable rung out end to end against the terminal plans E-10, E-11; shields earthed at the panel end only | All correct | ☐ |
| 1.7 | Field devices mounted at the right points: LSL-201 at 5 % of T-201, LSL-311…313 at 10 % of the stock tanks, LSL-531 in the pad sump, PSL-541 set to 1.0 bar, end limits on the vent and net drives | Recorded | ☐ |
| 1.8 | Vent and net drives free by hand over the full stroke; no obstruction in the roof | Free | ☐ |

## Phase 2 — Power-up (measure before closing the next breaker)
| # | Step | Acceptance | ☐ |
|---|---|---|---|
| 2.1 | Close -Q0 with every MCB and MPCB open; measure L1-L2-L3, L-N and phase rotation at -X1 | 400 / 230 V ± 10 %, clockwise | ☐ |
| 2.2 | Close -F1; measure -G1 output | 24.0 V ± 1 % | ☐ |
| 2.3 | Close -F21: coupler -A1, PLC -A10 and switch -A11 boot; ping 192.168.10.1 / .10 / .20 / .30 (E-14) | All answer | ☐ |
| 2.4 | Upload `plc/greenhouse.st` ([openplc.md](openplc.md) §3); PLC in RUN; HMI comms OK, heartbeat running | Heartbeat 20 per s on the HMI | ☐ |
| 2.5 | Coupler clock synchronised by NTP; HMI clock = real local time (WIB) | Within 1 min, no A01 | ☐ |
| 2.6 | Close -F22, -F23, -F24, then -F3 and -F4; test both RCDs with the RCD tester and the test button | Trip ≤ 30 mA, ≤ 300 ms | ☐ |

## Phase 3 — Safety circuit (before any actuator runs)
| # | Test | Acceptance | ☐ |
|---|---|---|---|
| 3.1 | Close -F25. Press -S0.1, then -S0.2 | -K0 drops, 24V-S dead (measure at -A1.3 1L+), A00 on the HMI | ☐ |
| 3.2 | Release; press only the HMI RESET | Nothing restarts; 24V-S stays off until -S0R | ☐ |
| 3.3 | -S0R, then RESET | 24V-S back; no output energises by itself | ☐ |
| 3.4 | Open one channel (lift wire 601, then 604); try -S0R | -K0 cannot be reset | ☐ |
| 3.5 | EDM: lift wire 609 (EDM loop through -K201/-K541 21-22); try -S0R | Reset refused | ☐ |

## Phase 4 — I/O checkout (loop check)
Work through **every row** of the [I/O checkout sheet](IO_CHECKOUT.md): 25 DI, 22 DO, 15 AI, 3 AO, plus its safety section S1…S8. Outputs are tested from **IRR MANUAL** / **CLIM MANUAL** on the HMI, so the PLC interlocks stay active. The stack light is the only output forced from the Editor debugger.

## Phase 5 — Device function tests (water only, no fertiliser yet)
| # | Test | Acceptance | ☐ |
|---|---|---|---|
| 5.1 | Bump test every motor (≤ 1 s): P-201, P-531, P-541, F-601…603 | Correct rotation (fans blow out of the house) | ☐ |
| 5.2 | Run each motor; current per phase | Balanced, ≤ nameplate | ☐ |
| 5.3 | Vent: full stroke closed → open → closed in CLIM MANUAL; time each stroke | 110–130 s (the PLC's travel supervision allows 180 s); stops on its own end limits | ☐ |
| 5.4 | ZT-511: read at both limits; correct the transmitter zero/span until 0.0 % / 100.0 % | ± 1 % at both ends | ☐ |
| 5.5 | Shade net: full stroke both ways | 80–100 s (supervision 150 s); stops on its end limits | ☐ |
| 5.6 | Stroke XV-201, XV-301, XV-401…404 from IRR MANUAL | Open and close; **XV-301 seat leak test**: return line quiet with the valve closed and P-201 running on a zone | ☐ |
| 5.7 | Dosing pumps with water: 100 % for 3 min into a measuring cylinder | P-311/P-312: 38–42 L/h, P-313: 9.5–10.5 L/h (FDS §3.2). Record | ☐ |
| 5.8 | Fog: P-541 in CLIM MANUAL, check every nozzle; close the supply valve | Even fog, no dripping nozzle; -K541 drops on low inlet pressure (A45) | ☐ |
| 5.9 | Pads: P-531 for 10 min | Whole pad face evenly wet; sump refills by its float valve | ☐ |

## Phase 6 — Hydraulic calibration (P-201 on water)
| # | Step | Acceptance | ☐ |
|---|---|---|---|
| 6.1 | **FT-201 check**: run zone 1 into a timed bucket test of 10 drippers, and compare FT-201 with a clamp-on flowmeter | FT-201 within ± 3 % | ☐ |
| 6.2 | **Zone reference flows**: run each zone 2 min with the return closed; set `SP_FLOW_Z1…Z4` to the measured FT-201 value (Settings page) | Recorded; each within 1 000–1 500 L/h | ☐ |
| 6.3 | **Dripper uniformity**: bucket-test 5 drippers spread over each zone for 2 min | Coefficient of variation ≤ 7 % | ☐ |
| 6.4 | Pressure: PT-201 during each zone shot; local gauge at the far end of each zone | PT-201 2.8–3.6 bar; far end ≥ 1.5 bar (pressure-compensated range) | ☐ |
| 6.5 | Shot volume: one IRRIGATE NOW with 20 L shots; check the delivered volume with the bucket test result | Within ± 5 % of the shot set point | ☐ |
| 6.6 | Drain: collect the Z1 drain gutter for one cycle; compare with FT-402 | Within ± 10 % | ☐ |

## Phase 7 — Interlocks, alarms and weather overrides (witnessed)
Prove every line of the cause & effect matrix ([FDS §11](FDS.md#11-interlocks)) on the real plant, using the FAT IDs as the test list: **SAF-01 … SAF-16**, **DEV-01 … DEV-08**. Simulate conditions safely:
- **Signal faults**: lift a wire at -X3 (A20…A35, each with its fallback).
- **Pressure high (A05)**: close a manual valve slowly with one zone running; watch PT-201 trip at 3.9 bar.
- **Dry run (A02)**: lift LSL-201's signal wire.
- **Motor faults**: trip each MPCB with its test button while running (A04, A14…A16, A38…A45).
- **Weather overrides** (CLI-04…06):
  - wet the rain sensor;
  - simulate ST-101 at 11 m/s, then 16 m/s, with the loop calibrator;
  - watch the vent and net limits take over.

## Phase 8 — Fertigation start-up and loop tuning
| # | Step | Acceptance | ☐ |
|---|---|---|---|
| 8.1 | **Water analysis** (lab or field kit): EC, pH and **alkalinity (mmol/L HCO₃⁻)** of the irrigation water | Recorded. The acid feedforward depends on it | ☐ |
| 8.2 | Set `FF_ACID` from the alkalinity: start at 13 × (measured alkalinity / 3.0) % per 1 000 L/h; acid circuit filled with 10 % HNO₃ (acid into water, PPE) | Recorded | ☐ |
| 8.3 | Mix stock A and B to recipe; check each with a diluted EC test (1 : 100 dilution, A and B equal) | A and B within ± 5 % of each other | ☐ |
| 8.4 | Calibrate AIT-301 (EC standard) and AIT-302/303 (pH 4 and 7, one probe at a time) | As-found / as-left recorded | ☐ |
| 8.5 | IRRIGATE NOW at the default set points (EC 2.5, pH 5.8): time to band in PRE-MIX, overshoot | In band ≤ 60 s; EC overshoot ≤ 0.3 mS/cm; pH never below 5.0 | ☐ |
| 8.6 | While watering: EC and pH from AIT-301/302 against a hand-held meter **at a dripper** | Within ± 0.1 mS/cm and ± 0.1 pH | ☐ |
| 8.7 | Zone changeovers: EC/pH trend on the Fertigation page | No HOLD at changeover | ☐ |
| 8.8 | If 8.5–8.7 fail: retune with the constants in [FDS §15](FDS.md#15-constants-var-constant) (EC: Kp 8, Ti 12 s, I-zone 0.5; pH: Kp 5, Ti 12 s, I-zone 0.5) using `tools/tune_dosing.py` on a plant model updated with the measured alkalinity and pump capacities | Final constants recorded | ☐ |

## Phase 9 — Climate set-up with the grower
| # | Step | Acceptance | ☐ |
|---|---|---|---|
| 9.1 | Enter the crop set points: vent and cooling temperature, RH limit, fog VPD, shade-net radiation, wind and storm limits | Recorded on the Settings page (value "In PLC") | ☐ |
| 9.2 | Positioner accuracy in CLIM MANUAL at 25 / 50 / 75 % (CLI-03) | ± 2 % against the vent by eye and ZT-511 | ☐ |
| 9.3 | Hot afternoon: watch VENT → COOL-START → PRE-WET → COOL; fan staging; return to VENT in the evening | Sequence as FDS §8; vents closed before the fans start | ☐ |
| 9.4 | Compare TT-501/MT-501 with the reference thermo-hygrometer in the aspirated box | ± 0.5 °C, ± 3 %RH | ☐ |

## Phase 10 — Site Acceptance Test (SAT)
Three consecutive days of automatic operation with the crop, no operator intervention:
- Every irrigation cycle completes. EC and pH are in band at every shot (Trends page, 10 min view, spot checks). Drain 20–40 % by day 3.
- Greenhouse temperature ≤ 35 °C. Cooling switches VENT ↔ COOL no more than 4 times per day (PRD NFR-09).
- No unexplained alarm. Every alarm that occurred has its cause recorded.
- **Restart tests**:
  - Power cut during a shot: the PLC cold-starts in AUTO with the program enabled and needs -S0R and RESET (FDS §13).
  - Coupler network cable unplugged: trip with A00 within 1 s.
  - HMI PC off: irrigation continues.
- The client signs the SAT.

## Handover package
- As-built drawings, with red-lines incorporated (`tools/drawings`, revision B).
- Final `greenhouse.st`, with its git commit and the OpenPLC upload log.
- Signed I/O checkout, FAT part B and SAT sheets.
- Commissioning records:
  - set points and tuned constants;
  - water analysis;
  - zone reference flows and dripper uniformity;
  - motor currents and insulation values (maintenance baseline).
- [Troubleshooting guide](TROUBLESHOOTING.md), including the preventive-maintenance plan.
- Spare-parts list and the operator training record.
- The troubleshooting trainer in the HMI simulation panel, for training new staff.
