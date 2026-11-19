# GH-1 Tropical Greenhouse — PLC control system: scope (draft, 2026-11-19)

Portfolio project #2, built on the `plc-batch-station` template (same toolchain, same verification approach). This file records what was agreed before any code is written.

## Agreed decisions
| Topic | Decision |
|---|---|
| Plant size | **Standard**: 1 greenhouse, 4 drip zones, inline fertigation skid, climate control, weather station |
| Climate | **Tropical lowland** (Indonesia): cooling-dominant, no heating, humidity handling |
| Deliverables v1 | **Core first**: ST program, plant sim, web HMI, automated FAT, PRD, FDS, README, CI |
| OpenPLC | **Yes, at the end**: STruC++ compile check in CI + FAT part B on Runtime v4 (WSL2 Docker) |

## The plant (defaults, adjustable)
- **Greenhouse GH-1**: about 1 000 m² plastic-film house, fruiting vegetables (chili/tomato) on cocopeat slabs, drip irrigated.
- **Water supply**: raw-water tank T-201 (level transmitter, low-level switch), main irrigation pump P-201 with pressure (PT) and flow (FT) transmitters.
- **Fertigation skid FS-300** (inline injection on a mixing loop, NetaJet style): stock tanks A, B and acid, three dosing pumps, EC and pH transmitters (pH duplicated for sensor validation). Water goes to the zones only when EC/pH are in band, otherwise it recirculates.
- **Irrigation zones Z1–Z4**: one solenoid valve each, run one at a time by a zone sequencer. Start on accumulated solar radiation (J/cm²) or on a fixed interval, within a day window. Shot size is metered by the flow totalizer. Drain flow is measured and reported as drain %.
- **Climate**: roof vents (analog position + feedback), shade screen (open/closed limits), pad-and-fan cooling (3 fan stages + pad pump), high-pressure fogging. Temperature/RH sensors inside, VPD calculated.
- **Weather station**: solar radiation, outside temperature/RH, wind speed, rain switch.

## Control functions
- Staged cooling: vents → shade screen → fogging → pad-and-fan. **Interlock**: pad-and-fan only with vents closed (otherwise it pulls hot outside air through the vents).
- Weather overrides: vents close on high wind or rain; screen retracts on storm wind.
- PI loops: EC (A/B dosing), pH (acid dosing), vent position on temperature. Dosing loops have transport dead time, tuned and documented.
- Irrigation sequencer: radiation-sum or timed start, minimum interval, max shots per day, per-zone shot volume, skip-on-fault and continue.
- Device blocks reused from the template: `FB_Motor`, `FB_Valve`, `FB_AnalogIn` (NAMUR NE 43 wire-break), `FB_PIControl`; plus a new `FB_Actuator` for the vent (position, travel timeout).
- Protection: E-stop for pumps, pump dry-run (T-201 low), high/low line pressure (blocked line/burst pipe), per-zone flow deviation (clogged or broken drippers), acid pump only with loop flow, stock-tank low levels, EC/pH high-high stops irrigation, motor feedback supervision, fail-safe inputs. FDS will state what each output does on PLC stop or power loss.
- CO2: measured and alarmed only. Enrichment is out of scope because an open-vent tropical house loses it.
- Modes: AUTO/MANUAL per device, operator setpoints (recipe: EC, pH, radiation threshold, shot volume, temperature/RH targets).
- Time: the plant publishes the **time of day** as an input register (stand-in for an I/O clock module; portable ST has no RTC). A **fast-forward demo** runs the PLC VM and the plant together in virtual time (default 20×, one day in 72 min), so every timer and loop behaves exactly as at 1×. *(Revised in phase 1: accelerating only the plant, as first drafted at 60×, would have made PLC timers and radiation sums wrong.)*
- Water quality: fog and pad water come from the clean supply line, because T-201 receives returned nutrient solution. *(Added in phase 1.)*

## Software (reused from the template)
- New package `farmsim/`: copies of `stvm.py`, `modbus.py`, `softplc.py`, `bench.py` from `plc-batch-station` (credited in CREDITS.md); new `plant.py` (greenhouse energy and water-vapour balance, substrate water content, EC/pH mixing with dead time, weather day cycle), `tags.py`, `hmi.py` + web pages (overview, irrigation, fertigation, climate, alarms, trends).
- Same address map approach as the template, so the plant and HMI work unchanged against OpenPLC Runtime v4.
- Tools reused and adapted: `check_openplc_compile.py`, `make_openplc_project.py`, `openplc_runtime.ps1`, `export_plcopen.py`.
- FAT target: about 80 automated tests (functional, safety, diagnostics), traced from the PRD.

## Phases
1. **PRD + FDS**: requirements, I/O list, sequences, cause & effect matrix, alarm list, Modbus register map. Review with you before coding.
2. **Plant model + ST program + soft-PLC**, FAT written alongside.
3. **Web HMI** + README + CI (pytest + STruC++ compile).
4. **OpenPLC Runtime v4 FAT part B** (WSL2 Docker, existing route; you type the runtime login).
5. *Later phase, not v1*: electrical drawings, I/O checkout, commissioning, troubleshooting trainer and fault library, technical report.

## Out of scope for v1
Second compartment, drain-water recirculation/UV disinfection, source-water selection, CO2 enrichment, heating, vendor ports (TIA Portal/CODESYS), real hardware.

## Repository rules
Local git repo on `main`, commits with the GitHub no-reply identity, upstream work credited in CREDITS.md. Not pushed until you say so.
