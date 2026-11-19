# Product Requirements Document — GH-1 Tropical Greenhouse

| | |
|---|---|
| **Document** | PRD-GH1, revision A |
| **Status** | Phase 2 done: every requirement in §6 has an automated test in `tests/`, named after the IDs below. HMI (phase 3) and OpenPLC part B (phase 4) to follow |
| **Related** | [Scope](SCOPE.md) · [Functional Design Specification](FDS.md) |
| **Template** | Built on the `plc-batch-station` project (T-101): same toolchain, address conventions, device blocks and verification approach |

---

## 1. Summary

A PLC control system for a 1 000 m² tropical lowland greenhouse that grows fruiting vegetables (chili, tomato) on cocopeat slabs. It controls three things:

- **Irrigation**: a water tank with automatic refill, a main pump and four drip zones run by a zone sequencer. Cycles start on accumulated solar radiation or on an interval, within a day window.
- **Fertigation**: inline injection of nutrient stock A and B and acid on a mixing loop, with EC and pH control. Water goes to the crop only when EC and pH are in band.
- **Climate**: roof vents, an external shade net, high-pressure fogging and pad-and-fan evaporative cooling, staged by a climate state machine with weather overrides (rain, wind, storm).

The control logic is **IEC 61131-3 Structured Text** for **OpenPLC v4**. Field I/O and the HMI connect over **Modbus TCP**. A virtual plant (weather, greenhouse air, crop, hydraulics and water chemistry) replaces the hardware, so the system runs and is tested on a laptop. The *same* `.st` file is uploaded unchanged to OpenPLC Runtime v4.

## 2. Problem and motivation

The first portfolio project (T-101) shows a classic batch sequence. Agriculture and horticulture automation is different and is a growing field in Indonesia:

- the process runs **continuously, day and night**, driven by **time of day and weather**, not by an operator's START;
- several **independent subsystems** (irrigation, fertigation, climate) share field I/O and must not fight each other (pad-and-fan with open vents is the classic mistake);
- control includes **ratio control with dead time** (dosing into a moving water stream), a **3-point step positioner** (vent motor) and **staged equipment** (fans);
- **crop safety** matters as much as personnel safety: a wrong EC or pH can kill a crop in one irrigation cycle.

This project shows those skills on one realistic installation, with no paid software or hardware.

## 3. Goals and non-goals

### Goals
| ID | Goal |
|---|---|
| G1 | Control irrigation, fertigation and climate of a realistic greenhouse in IEC 61131-3 Structured Text. |
| G2 | Engineer protection layers: personnel safety (E-stop), equipment protection (dry-run, dead-head, pressure, motor feedback), crop safety (EC/pH limits, sensor validation) and weather protection. |
| G3 | Give every function a defined degraded mode when a sensor fails (fallback, not just an alarm). |
| G4 | Integrate PLC, remote I/O and HMI over Modbus TCP using OpenPLC's address map. |
| G5 | Verify every functional, safety and diagnostic requirement with an automated test, in CI. |
| G6 | Let anyone run a full simulated day in about an hour (fast-forward demo), with no hardware or licences. |
| G7 | Produce the documents a client expects: PRD, FDS with I/O list, cause & effect matrix, alarm list and register map; FAT. |

### Non-goals (v1)
- Not a certified safety system. The E-stop in the PLC is secondary to a hardwired safety relay (§11).
- No second compartment, drain-water recirculation/UV disinfection, source-water selection, CO2 enrichment or heating (see [Scope](SCOPE.md)).
- No crop-growth model, recipe database or data logging to a historian.
- Electrical drawings, I/O checkout, commissioning procedure, troubleshooting trainer and technical report are **phase 5**, after v1.

## 4. Users and stakeholders

| Persona | Needs | Served by |
|---|---|---|
| **Grower** | Set EC, pH, irrigation and climate targets; see at a glance that the crop gets water and the house is not overheating | Settings pages with PLC-side limits, overview mimic, daily water/drain report |
| **Farm operator** | Start/stop irrigation, irrigate now, acknowledge alarms, run devices by hand | Panel push-buttons, HMI controls, MANUAL modes, alarm list |
| **Maintenance technician** | Find why a device is not running, find leaks and clogged drippers | Interlock words, zone flow diagnostics, device status words, maintenance counters |
| **Controls engineer** (developer) | Change logic and know nothing broke | ST virtual machine, automated FAT, CI |
| **Reviewer / hiring manager** | Judge engineering ability quickly | README, this PRD, the FDS, one-command demo |

## 5. Process scope

| Tag | Equipment | Signal |
|---|---|---|
| GH-1 | Greenhouse, 1 000 m² plastic film, 4 drip zones of 250 m² | — |
| T-201 | Irrigation water tank, 5 m³ | — |
| XV-201 | Tank refill valve (well/mains) | DO |
| LT-201 / LSL-201 | Tank level transmitter / low-level switch (dry-run) | AI / DI |
| P-201 | Main irrigation pump, 1.5 m³/h at 3.2 bar (contactor + feedback) | DO + DI |
| FT-201 / PT-201 | Supply flow / pressure transmitters | AI |
| P-311 / P-312 / P-313 | Dosing pumps stock A / stock B / acid (run + speed, run feedback) | DO + AO + DI |
| LSL-311 / 312 / 313 | Stock tank low-level switches | DI |
| AIT-301 | EC transmitter | AI |
| AIT-302 / AIT-303 | pH transmitters, duplicated (1oo2 with validation) | AI |
| XV-301 | Return valve (mixing loop back to T-201) | DO |
| XV-401 … XV-404 | Zone valves Z1–Z4 | DO |
| FT-402 | Drain flow, reference gutter in Z1 | AI |
| RT-101, TT-101, MT-101, ST-101, XS-105 | Weather station: solar radiation, outside temperature, outside RH, wind speed, rain detector | AI / DI |
| TT-501, MT-501, AT-502 | Greenhouse air temperature, RH, CO2 | AI |
| M-511 / ZT-511 / ZSO-511 / ZSC-511 | Roof vent reversing motor / position transmitter / open and closed limit switches | 2 DO + AI + 2 DI |
| M-521 / ZSO-521 / ZSC-521 | External shade net reversing motor / open (retracted) and closed (deployed) limits | 2 DO + 2 DI |
| F-601 / F-602 / F-603 | Pad-and-fan exhaust fans (contactor + feedback) | DO + DI |
| P-531 / LSL-531 | Pad pump / pad sump low level | DO + DI |
| P-541 | High-pressure fog pump | DO + DI |
| — | I/O clock module (time of day), E-stop chain, START / STOP (NC) / RESET push-buttons, stack light | IR / DI / DO |

The full I/O list with addresses is in [FDS §4](FDS.md#4-io-list): 25 DI, 16 AI, 22 DO, 3 AO.

## 6. Functional requirements

Each requirement lists the automated test that verifies it. Test IDs: IRR irrigation, FER fertigation, CLI climate, SAF safety and protection, DEV devices and diagnostics, COM communication.

### 6.1 Irrigation
| ID | Requirement | Test |
|---|---|---|
| FR-01 | In AUTO, START enables the irrigation program. STOP in IDLE disables it. With the program disabled, no automatic cycle starts. | IRR-01 |
| FR-02 | Inside the day window, a cycle starts when the radiation sum since the last cycle start reaches the threshold **and** the minimum interval has passed, **or** when the maximum interval has passed. | IRR-02, IRR-03 |
| FR-03 | No automatic cycle starts outside the day window or after the daily maximum number of cycles. | IRR-04 |
| FR-04 | The first cycle of the day starts at the window start (the maximum interval has passed since yesterday's last cycle). | IRR-05 |
| FR-05 | IRRIGATE NOW starts one cycle in AUTO from IDLE, regardless of window, program enable and counters. Interlocks still apply. | IRR-06 |
| FR-06 | A cycle runs PRE-MIX → enabled zones in order Z1…Z4 → RUN-DOWN → IDLE. Disabled zones are skipped. | IRR-07 |
| FR-07 | Each zone receives its set shot volume within ± 2 %, metered by FT-201. | IRR-08 |
| FR-08 | Zone changeover is open-before-close: the next valve opens, the previous one closes 2 s later. P-201 never runs without an open flow path. | IRR-09, SAF-04 |
| FR-09 | STOP during PRE-MIX, SHOT or HOLD pauses the cycle with all irrigation outputs off. START resumes with PRE-MIX and then delivers only the *remaining* volume of the interrupted zone. ABORT cancels the cycle. STOP during RUN-DOWN ends the cycle. | IRR-10, IRR-11 |
| FR-10 | The radiation sum integrates RT-101 (J/cm² = Σ W/m² · s / 10 000) and restarts at each cycle start. | IRR-12 |
| FR-11 | At midnight the daily counters (cycles, water, drain %) are copied to "previous day" and reset. | IRR-13 |
| FR-12 | T-201 is refilled automatically: XV-201 opens below 40 % and closes at 85 %. | IRR-14 |
| FR-13 | Setpoints outside their limits are clamped by the PLC, and the clamped value is written back so the HMI shows the value in force. | IRR-15 |
| FR-14 | Irrigation MANUAL mode can be entered only from IDLE or FAULT. Each device can then be run on its own, with all interlocks active. | IRR-16 |
| FR-15 | Time of day comes from the I/O clock register. If the clock fails, the day window is replaced by a daylight test (radiation ≥ 50 W/m²), so the crop is still watered. | IRR-17 |

### 6.2 Fertigation
| ID | Requirement | Test |
|---|---|---|
| FE-01 | Dosing runs only while P-201 pumps through the mixing loop (PRE-MIX, SHOT, HOLD). Stock A and B always run at the same speed (1 : 1). | FER-01 |
| FE-02 | EC control: flow-proportional feedforward plus PI trim. EC reaches the band within 60 s of PRE-MIX start and holds SP ± 0.05 mS/cm at steady flow. | FER-02 |
| FE-03 | pH control: flow-proportional acid feedforward plus reverse-acting PI trim. pH reaches the band within 60 s and holds SP ± 0.10. | FER-03 |
| FE-04 | Water goes to a zone only after EC and pH have been in band for 10 s. If either leaves the band for 10 s during a shot, the unit returns to recirculation (HOLD) and the zone continues once back in band. | FER-04, FER-05 |
| FE-05 | PRE-MIX or HOLD lasting 180 s trips the cycle (A10). | FER-06 |
| FE-06 | pH is measured by two probes. With both healthy, the average is used and a deviation > 0.3 for 10 s trips (A09). With one probe failed, the other is used (warning). With both failed, acid dosing is blocked and the cycle trips. | FER-07, FER-08 |
| FE-07 | EC and pH setpoint changes take effect at once, including during a cycle. | FER-09 |

### 6.3 Climate
| ID | Requirement | Test |
|---|---|---|
| CL-01 | In VENT state the vent position demand is the larger of the temperature demand (PI on TT-501 vs vent setpoint) and the humidity demand (proportional above RH max). | CLI-01, CLI-02 |
| CL-02 | The vent positioner drives M-511 open/close until ZT-511 is within ± 2 % of the demand (3-point step control with 0.5 s reversal pause). | CLI-03 |
| CL-03 | Rain limits the vents to the rain position. Wind ≥ wind limit caps them at 30 %. Wind ≥ storm limit closes them and retracts the shade net. | CLI-04, CLI-05, CLI-06 |
| CL-04 | The shade net deploys after 10 min above the radiation setpoint or when temperature ≥ vent SP + 4 °C. It retracts after 15 min below (setpoint − 150 W/m²) with temperature < vent SP + 2 °C. | CLI-07 |
| CL-05 | Fogging pulses (10 s on / 50 s off) in VENT state while VPD > fog setpoint and temperature > vent SP, and stops when VPD < setpoint − 0.3 kPa or RH ≥ 90 %. | CLI-08 |
| CL-06 | COOL is entered when temperature ≥ cool SP for 5 min and the vent demand is either ≥ 90 % or held back by weather. The vents close first; then the pads are pre-wetted for 60 s; then fans stage 1–3 on temperature. | CLI-09, CLI-10 |
| CL-07 | COOL is left after 10 min with temperature < cool SP − 3 °C. The pad pump stops and one fan runs 5 min to dry the pads, then the state returns to VENT. | CLI-11 |
| CL-08 | Climate MANUAL can be entered at any time: vent position, shade net, fans, pad pump and fog pump are operated from the HMI with all interlocks active. Leaving MANUAL returns to VENT. | CLI-12 |

### 6.4 Safety and protection
| ID | Requirement | Test |
|---|---|---|
| SR-01 | E-stop removes all outputs, trips irrigation, and needs RESET after release. No automatic restart. | SAF-01 |
| SR-02 | P-201 is blocked when LSL-201 shows the tank dry (dry-run). | SAF-02 |
| SR-03 | PT-201 ≥ 3.9 bar for 1 s stops P-201 and trips (blocked line). PT-201 < 0.8 bar with the pump running for 15 s trips (burst pipe or lost prime). | SAF-03 |
| SR-04 | P-201 is permitted only with a flow path: XV-301 or a zone valve commanded (dead-head protection). | SAF-04 |
| SR-05 | Dosing pumps are permitted only with P-201 confirmed running and flow ≥ 500 L/h for 3 s, their stock tank not low, and their analyser healthy. A low A or B tank stops both A and B. | SAF-05, SAF-06 |
| SR-06 | EC ≥ SP + 1.0 mS/cm for 5 s (A07) or pH ≤ 4.5 for 5 s (A08) blocks the zone valves and the related dosing pumps (A07: A/B, A08: acid) and trips the cycle (crop protection). | SAF-07, SAF-08 |
| SR-07 | Fans are permitted only with the vents closed (ZSC-511 made, or ZT-511 ≤ 5 %). The vents cannot open while any fan is commanded. | SAF-09 |
| SR-08 | Open and close contactors of a reversing motor are never on together, with a 0.5 s pause on reversal. A motor stops at its end limit. | SAF-10 |
| SR-09 | A vent that does not move (< 1 % in 15 s) or a shade net that does not reach its limit in 150 s raises a travel fault and locks out that actuator until RESET. A tripped motor-protection breaker also locks it out. | SAF-11, SAF-12 |
| SR-10 | Motor command/feedback discrepancy for 2 s raises an alarm and locks out that motor until RESET (irrigation and dosing pumps also trip the cycle). | SAF-13 |
| SR-11 | A 4–20 mA signal below 3.6 mA (NAMUR NE 43) is a signal fault: it acts on interlocks at once, alarms after 1 s, and switches the function to its defined fallback (FDS §12). | SAF-14 |
| SR-12 | The shade net may not deploy at storm wind. A failed wind sensor is treated as storm. A failed rain detector (NC, open) is treated as rain. | SAF-15 |
| SR-13 | Fog is blocked when greenhouse RH ≥ 90 % or MT-501 has failed. Fog and pad water come from the clean supply line, never from T-201 (which receives returned nutrient solution); the fog pump stops itself on low inlet pressure, seen as a feedback discrepancy. The pad pump is blocked when the pad sump is low. | SAF-16 |
| SR-14 | Loss of remote-I/O communication zeroes the inputs, so the system trips (A00). The I/O coupler watchdog de-energises the outputs after 1 s. | COM-01, COM-02 |
| SR-15 | Alarms latch. RESET clears only alarms whose condition has gone. | SAF-01 |

### 6.5 Diagnostics and maintenance
| ID | Requirement | Test |
|---|---|---|
| DR-01 | Every motor and valve is an instance of a standard block (`FB_Motor`, `FB_Valve`, `FB_Actuator`) with a common status word. | DEV-01 |
| DR-02 | Every device group publishes an interlock word naming each missing permissive, so the HMI shows *why* a device is held off. | DEV-02 |
| DR-03 | Zone flow is compared with the zone reference flow after 20 s: > +25 % raises *flow high* (leak, broken dripper), < −25 % raises *flow low* (clogged drippers, valve not opening). A shot not complete in 2 × its expected time is skipped (*shot timeout*). The affected zone is shown in a diagnostic word. | DEV-03, DEV-04, DEV-05 |
| DR-04 | Daily drain % for the reference zone is calculated from FT-402 and alarmed outside 10–50 % after 5 cycles. | DEV-06 |
| DR-05 | The PLC counts motor starts, running minutes, valve cycles and vent reversals for maintenance. | DEV-07 |
| DR-06 | A stack light on the irrigation panel shows running (green), attention (amber) and trip (red, flashing when RESET is needed). | DEV-08 |

### 6.6 HMI
| ID | Requirement |
|---|---|
| HR-01 | Overview mimic: tank, pump, dosing skid, zones, greenhouse with vent, shade net, fans, pads and fog, live values and states. |
| HR-02 | Irrigation page: program state, step, active zone and volume, radiation sum, time since last cycle, daily and previous-day water, cycles and drain %, zone diagnostics. |
| HR-03 | Fertigation page: EC, pH A/B/used, setpoints and bands, dosing outputs, stock tank states. |
| HR-04 | Climate page: climate state, vent demand and position, weather, inside temperature/RH/VPD/CO2, active overrides (rain, wind, storm, fallback). |
| HR-05 | Controls enabled only when the PLC would accept them: START, STOP, RESET, IRRIGATE NOW, ABORT, AUTO/MANUAL per subsystem. |
| HR-06 | Settings pages with limits shown, download to the PLC, and read-back of the value in force. |
| HR-07 | Alarm list (active vs cleared-but-not-reset), header banner, and the device's interlock reasons. |
| HR-08 | Trends: 24 h of temperature, RH, vent position and radiation; 10 min of EC, pH and flow. |
| HR-09 | Communications watchdog from the PLC heartbeat. |
| HR-10 | ISA-101 palette: grey for normal, colour only for abnormal. |
| HR-11 | A separate *field simulation* panel (demo only): weather scenario, time of day, fast-forward speed, fault injection. Not part of the operator HMI. |

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | PLC task cycle 50 ms. |
| NFR-02 | Standard IEC 61131-3 ST, no vendor extensions; passes the strict-typing VM and the STruC++ compiler. |
| NFR-03 | The same `.st` file runs in the soft-PLC, the fast-forward demo and OpenPLC Runtime v4. |
| NFR-04 | Process time base accurate to 0.5 % (radiation sum, intervals, shot timing). The template's self-resetting 1 s timer (≈ 5 % slow) is not good enough. |
| NFR-05 | Fast-forward demo at ≥ 20× real time (one day in ≤ 72 min) with PLC and plant advancing together, so every timer, PI loop and timeout behaves exactly as at 1×. |
| NFR-06 | Tests are deterministic, run in virtual time, and the full suite finishes in under 5 minutes on an ordinary PC. |
| NFR-07 | No paid software. Python standard library at runtime; pytest for tests. |
| NFR-08 | Every safety and protection requirement (§6.4) has at least one automated test. |
| NFR-09 | Climate performance in the simulation, on the default clear day (33 °C outside): greenhouse temperature ≤ 35 °C at all times and VENT/COOL switching no more than 4 times per day. |

## 8. System architecture

```
 ┌────────────────┐  Modbus TCP :5020   ┌──────────────────────────┐  Modbus TCP :5502 (OpenPLC :502)  ┌──────────┐
 │ Virtual plant  │◄───────────────────►│ PLC  greenhouse.st       │◄──────────────────────────────────►│ Web HMI  │
 │ remote I/O +   │ DI/IR → %IX/%IW100… │ soft-PLC  or  OpenPLC v4 │  %MW0…139 (holding 1024…1163)      │ :8080    │
 │ I/O clock      │ %QX/%QW100… → coils │                          │                                    │          │
 └────────────────┘                     └──────────────────────────┘                                    └──────────┘
```

Three run modes, one program:

| Mode | PLC | Plant link | Time | Use |
|---|---|---|---|---|
| Live | soft-PLC or OpenPLC Runtime v4 | Modbus TCP | real time, 1× | OpenPLC FAT, realism |
| Fast-forward demo | soft-PLC VM, in-process with the plant | direct (same wiring as the bench) | virtual, 1–30× (default 20×) | watching a full day |
| Test bench | VM, in-process | direct | virtual, as fast as possible | automated FAT |

| Component | File (planned) | Role |
|---|---|---|
| PLC program | `plc/greenhouse.st` | Irrigation sequence, fertigation loops, climate state machine, interlocks, alarms, HMI interface |
| ST VM, Modbus, soft-PLC, bench | `farmsim/stvm.py`, `modbus.py`, `softplc.py`, `bench.py` | Copied from `plc-batch-station`; soft-PLC gains the fast-forward mode |
| Virtual plant | `farmsim/plant.py`, `weather.py`, `plant_server.py` | Weather day cycle, greenhouse heat/vapour/CO2 balance, substrate and drain, hydraulics, EC/pH mixing with dead time, actuators, I/O clock, faults |
| HMI | `farmsim/hmi.py`, `farmsim/web/` | Modbus client, JSON API, single-page operator UI |
| Tag map | `farmsim/tags.py` | Single source of truth for the register map (FDS §9) |

## 9. Interfaces

- **PLC ↔ remote I/O** (OpenPLC remote device **PLANT**): DI 0–31 → `%IX100.0–%IX103.7` (25 used), IR 0–15 → `%IW100–115`, coils 0–23 ← `%QX100.0–%QX102.7` (22 used), HR 0–2 ← `%QW100–102`.
- **PLC ↔ HMI**: OpenPLC Modbus server, `%MWn` = holding register `1024 + n`, `%MW0–139` used. The Modbus server's `%MW` count must be raised from the template's 64 to 256 (FDS §14, item 1). Commands are one-shot bits in `%MW0`.

## 10. Acceptance criteria

v1 is accepted when:
1. `pytest` passes locally and in GitHub Actions.
2. The fast-forward demo runs a default clear day from 05:00 to 19:00 with all cycles completed, EC/pH in band at every shot, and no alarms.
3. Every FR, FE, CL, SR and DR in §6 has a passing test, recorded in the FAT.
4. `plc/greenhouse.st` compiles with STruC++ (CI) and runs on OpenPLC Runtime v4 in WSL2 Docker, with FAT part B passing.

## 11. Assumptions, risks and limitations

| Item | Note / mitigation |
|---|---|
| Functional safety | The PLC E-stop is secondary. A real installation needs a hardwired safety relay that removes actuator power. The plant model does this itself. |
| Simulated plant | The greenhouse model is a lumped, uncalibrated model chosen to give plausible dynamics. PI gains and staging delays must be re-tuned on a real house. |
| Time of day | Portable IEC 61131-3 has no real-time clock function, and OpenPLC ST has no RTC access. The I/O clock register stands in for an NTP/GPS clock module. |
| OpenPLC `%MW` size | 140 HMI words exceed the 64 configured in the template. Raising the server's `%MW` count to 256 is expected to work, but is unverified until phase 4. Fallback: split the HMI map across `%MW` and `%IW`/`%QW` spares. |
| VM performance | The program is about twice the template's size. Fast-forward at 20× needs 400 scans/s; if the VM is too slow, the default speed drops. Measured in phase 2. |
| Modbus security | Modbus TCP has no authentication. Isolated control network or VPN only. |

## 12. Milestones

| Milestone | Status |
|---|---|
| P1 PRD + FDS (this document set) | Done |
| P2 Plant model, ST program, soft-PLC fast-forward, automated FAT | Done: automated FAT and full-day run pass; STruC++ compile clean |
| P3 Web HMI, README, CI (pytest + STruC++) | — |
| P4 OpenPLC Runtime v4 FAT part B | — |
| P5 Drawings, I/O checkout, commissioning, troubleshooting trainer, report | Later |

## 13. Future work
Second compartment, drain-water recirculation with UV disinfection, source-water selection (rain/well), CO2 enrichment, irrigation on substrate moisture sensors, weather-forecast inputs, historian and daily report export, Siemens TIA Portal or CODESYS port.
