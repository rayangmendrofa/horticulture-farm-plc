# GH-1 Tropical Greenhouse: design and verification of an irrigation, fertigation and climate control system in IEC 61131-3 Structured Text

*Technical project report · revision A · November 2026 · about 20 minutes to read*

## Abstract

This report describes the design and verification of the control system for GH-1, a 1 000 m² plastic greenhouse in the Indonesian lowlands, growing fruiting vegetables on substrate [2, 3]. One PLC program, written in IEC 61131-3 Structured Text for OpenPLC v4 with a 50 ms cyclic task, runs three jobs [1, 3]:
- **drip irrigation** of four zones, started on accumulated solar radiation;
- **fertigation**: inline dosing of two nutrient concentrates and acid on measured EC and pH;
- **climate control**: roof vents, a shade net, fogging and pad-and-fan cooling, overridden by rain, wind and storm.

No greenhouse was available, so the same source file was run in a purpose-built Structured Text interpreter. It is coupled over Modbus TCP to a physical model of the greenhouse and to a web HMI [2, 9]. The model covers weather, air temperature and humidity, crop transpiration, pump and dripper hydraulics, and carbonate water chemistry. A fast-forward mode advances PLC and plant together in virtual time, so a full day takes about an hour of wall time while every timer and control loop behaves exactly as in real time [3].

**Results:**
- **Automated tests:** 114 tests cover requirements, safety functions, diagnostics, the HMI, 48 simulated field faults, the electrical drawings and the interpreter. All pass on both interpreter modes; the third-party Modbus interoperability check runs in CI only [4].
- **A simulated clear day** at up to 33 °C outside:
  - the greenhouse stays at or below 32.4 °C;
  - 18 irrigation cycles deliver 4.4 m³ with 43.8 % drain;
  - every zone is watered at EC 2.48–2.50 mS/cm and pH 5.79–5.82;
  - no alarm is raised [4].
- **On the real toolchain:** the program compiles without errors or warnings on STruC++, the OpenPLC v4 compiler. On OpenPLC Runtime v4.3.2 a separate acceptance test passed 7 of 7 [5]:
  - the E-stop removed every field output in 98 ms;
  - loss of the remote I/O tripped the PLC in 0.06 s.

The project also delivers a 15-sheet electrical drawing set, an I/O checkout sheet, a commissioning procedure and a fault-finding trainer [6, 7, 8].

**Main open item:** the system has not run against physical wiring or a real crop [9].

## 1. Introduction

Water a tomato plant by hand and you decide three things: when it needs water, how much, and what is in the can. In a commercial greenhouse a PLC (programmable logic controller) makes those decisions dozens of times a day for thousands of plants. It also keeps the air cool enough for them to survive a tropical afternoon.

The difficult part is not opening a valve. It is the dependencies between the jobs:
- fertiliser must only reach the crop when the mix is right;
- a fan must not run with the roof open;
- a dosing pump must not inject acid into a pipe with no water flowing;
- a broken sensor wire must lead to a safe decision, not a silent wrong one.

This project is the second in a series. The first, a heated batch tank called T-101, established the toolchain and the verification method: Structured Text on OpenPLC, a soft-PLC that runs the real source file, a virtual plant over Modbus TCP, and requirements traced to automated tests [21]. GH-1 keeps that method and raises the difficulty in three ways:
- **continuous control:** dosing loops with dead time, and a positioning loop for the vent;
- **a process that depends on time of day and weather;**
- **about two and a half times the I/O:** 25 digital inputs, 22 digital outputs, 16 analog inputs and 3 analog outputs.

The report covers:
- the process (section 2) and architecture (3);
- the three control functions (4), then protection and safety (5);
- the verification method (6) and results (7);
- the field-side documents (8);
- what has not been proven (9) and what comes next (10).

## 2. The process

GH-1 is a 40 × 25 m single-span tunnel with a ridge vent, in the lowlands of Indonesia [3]. Daytime air outside reaches 33 °C, nights stay above 23 °C, and humidity is high, so the house needs cooling, never heating. Instruments are tagged in the ISA-5.1 style [16].

| System | Equipment (design values) |
|---|---|
| Water | Tank T-201 5 m³ (LT-201, LSL-201), refill XV-201, pump P-201 1.5 m³/h at 3.2 bar, flow FT-201, pressure PT-201 |
| Fertigation | Stock tanks A and B (1 : 100 concentrates) and 10 % nitric acid; dosing pumps P-311/P-312 (40 L/h) and P-313 (10 L/h) on 4–20 mA speed; 3 L mixing chamber; EC analyser AIT-301, two pH analysers AIT-302/303; return valve XV-301 to the tank |
| Irrigation | Four zones of 250 m², 625 pressure-compensated drippers each (1 250 L/h), valves XV-401…404, drain measurement FT-402 on zone 1 |
| Climate | Ridge vent M-511 (20 % of floor area, position ZT-511), external shade net M-521, fog pump P-541 (70 bar, 100 nozzles), pad pump P-531 and three exhaust fans F-601…603 (48 000 m³/h each) |
| Weather | Radiation RT-101, outside temperature and humidity TT-101/MT-101, wind ST-101, rain detector XS-105; inside TT-501, MT-501, CO₂ AT-502 |

A fertigation cycle works like a kitchen tap with two syrups and a squeeze of lemon:
1. **Pre-mix.** Water is pumped from the tank through the dosing point and back to the tank (the return loop) until the mix is right.
2. **Shots.** The zones receive the water one by one: a "shot" of a set volume each, metered by the flow transmitter.
3. **Changeover.** The next zone valve opens before the previous one closes, so the pump never pushes against a closed pipe.

The fog and pad water come from the clean supply, not from the tank: the tank holds returned nutrient solution, and nutrient spray clogs nozzles and burns leaves [3].

## 3. System architecture

```
 ┌────────────────┐  Modbus TCP   ┌───────────────────────────┐  Modbus TCP    ┌──────────┐
 │ Virtual plant  │◄─────────────►│ PLC: greenhouse.st        │◄──────────────►│ Web HMI  │
 │ remote I/O     │               │ soft-PLC  or  OpenPLC v4  │ %MW0–139       │          │
 └────────────────┘               └───────────────────────────┘                └──────────┘
```

Field I/O sits on a Modbus TCP remote-I/O coupler, which OpenPLC polls as a remote device every 50 ms [3, 11]. The PLC publishes a status block of 100 words (`%MW40–139`) and accepts commands, set points and manual requests in `%MW0–37`. The HMI uses nothing else, so it works unchanged against the soft-PLC and against OpenPLC [3, 5]. The interface is defined once, in `farmsim/tags.py`, and used by the HMI, the tests and the drawing generator.

The time of day comes from the I/O coupler's clock as a register (`CLOCK_MIN`), because portable Structured Text has no real-time clock. A frozen or impossible clock raises an alarm and switches the irrigation window to a daylight test [3].

## 4. Control program design

The program has two subsystems with their own AUTO and MANUAL modes: irrigation with fertigation, and climate [3]. Every output is the product of a *request* (from the sequence, a control loop or manual mode) and a *permissive* (the interlock word of that device). Manual mode never bypasses the permissive. Each pump, valve, fan and drive is an instance of a standard device block (`FB_Motor`, `FB_Valve`, `FB_Actuator`). These blocks supervise the running feedback or the travel and publish a status word. The HMI can therefore say *why* a device is held off, for example "F-601 blocked: vents not closed" [3].

### 4.1 Irrigation

**Starting a cycle.** A cycle starts, inside a day window (06:30–17:00 by default), when either condition holds:
- the radiation summed since the last cycle reaches 130 J/cm² and at least 20 minutes have passed;
- 120 minutes have passed.

This is common soilless-culture practice: water use follows sunlight [3]. The PLC sums radiation once per second from a time base that counts scans, not a self-resetting timer. A self-resetting timer would lose part of a scan every second, about 5 % at this task rate [3].

**The sequence.** IDLE → PRE-MIX → SHOT → RUN-DOWN:
- **PRE-MIX** circulates through the return until EC and pH have been in band for 10 s.
- **SHOT** meters each enabled zone. If EC or pH leave the band for 10 s, the cycle falls back to HOLD (recirculate, then resume the same zone and volume).
- **RUN-DOWN** stops dosing first, closes the zone valve, then stops the pump.
- **STOP** pauses mid-cycle and resumes with the interrupted zone's remaining volume. **ABORT** cancels.

**Supervision.** Each zone's flow is compared with its reference after 20 s:
- above +25 % raises a *leak* warning;
- below −25 % raises a *clogged* warning;
- a shot that takes more than twice its expected time is skipped.

### 4.2 Fertigation

Dosing uses ratio control with feedback trim. The feedforward term is proportional to the measured water flow, so dosing follows the pump from the first second. A PI controller corrects the remaining error [3].

| Loop | Feedforward | PI tuning (final) |
|---|---|---|
| EC → P-311 and P-312 together | `(SP − 0.3) × flow / 80` % | Kp 8 %/(mS/cm), Ti 12 s, integration zone ±0.5 |
| pH → P-313 (reverse acting) | `13 × flow [m³/h]` % | Kp 5 %/pH, Ti 12 s, integration zone ±0.5 |

**Deliberate off-design.** The simulated plant does not match the design data:
- the stock solution is mixed 10 % too strong;
- the water's alkalinity is 3.4 instead of 3.0 mmol/L.

With feedforward alone, EC would settle at 2.75 and pH at 6.0, both outside the band. The trim has real work to do, as it would on site [3].

**Integration zone.** The PI block integrates only while the error is inside the zone. During start-up, when the error is large, the integral therefore cannot wind up and cause overshoot.

**Two pH probes (1oo2 with fallback).** They are compared continuously. If they disagree, irrigation trips (A09), because nobody can tell which one is right. If one probe's signal fails, control continues on the other.

**Crop protection.** EC high-high (A07) and pH low-low (A08) close every zone and trip irrigation. They are checked only while water is flowing: the analysers measure stagnant water otherwise.

### 4.3 Climate

A state machine runs VENT → COOL-START → PRE-WET → COOL → PAD-DRY:
- **VENT.** The vent position follows the larger of a temperature demand and a humidity demand. Fogging pulses 10 s on and 50 s off when the air is dry (VPD from the FAO-56 vapour-pressure equation [12]). The shade net deploys on high radiation.
- **Entering COOL.** The house must stay hot for 5 minutes with the vents already at their limit. The vents then close, the pads are wetted for 60 s, and fans start in stages of one to three.
- **Leaving COOL.** One fan keeps running over the dry pads for 5 minutes, so they don't stay wet and grow algae.

Pad-and-fan only works with the vents closed: otherwise the fans pull hot outside air through the roof instead of through the wet pads. This interlock is enforced in both directions [3, 20].

**Weather limits** apply in AUTO and in MANUAL:
- **rain:** the vent is held at 10 %;
- **wind above 10 m/s:** the vent is capped at 30 %;
- **storm above 15 m/s, or a failed wind sensor:** the vents close and the net retracts.

**The vent drive.** It is a reversing motor with no speed control. A 3-point step positioner in `FB_Actuator` moves it in pulses towards the set point (stop band ± 0.5 %), with a 0.5 s pause before every reversal, and supervises the travel time. A jammed vent is detected within 15 s of a stall (A36).

### 4.4 Diagnostics and maintenance

**Alarms.** 49 alarms in four classes:
- **trip:** stops irrigation;
- **lock-out:** blocks one device until RESET;
- **alarm:** needs attention;
- **warning:** informs.

Alarms latch until RESET, and the HMI keeps a cleared-but-not-reset alarm visible, so the first cause of a cascade is not lost. A stack light on the panel shows running, attention and trip.

**Analog signals.** Every analog input is checked for the NAMUR NE 43 fault level (below 3.6 mA [14]). Each has a defined fallback, from "use the other pH probe" to "assume a storm".

**Maintenance counters.** The PLC counts motor starts and running minutes, valve cycles and vent reversals.

## 5. Protection and safety design

**Hardwired E-stop.** Two E-stops, on the panel door and at the fertigation skid, act through a two-channel safety relay. The relay switches the 24 V rail that feeds every contactor coil and solenoid valve (stop category 0, IEC 60204-1 [17]). An E-stop therefore de-energises the field whatever the PLC does. The relay's reset is monitored and includes the feedback contacts of the main pump and the 70 bar fog pump: a welded contactor blocks the reset. The PLC only *monitors* the E-stop (`ESTOP_OK`). After a reset it still needs an operator RESET and START, so nothing restarts by itself [8].

**Protection functions** are implemented in the PLC and are not safety functions in the ISO 13849 sense [18]:

| Function | How |
|---|---|
| Pump dry-run | Independent low-level switch LSL-201, not the level transmitter |
| Dead-head and burst | Pump permitted only with a flow path open; pressure high (3.9 bar) and low trips |
| No acid without flow | Dosing permitted only with P-201 running **and** flow ≥ 500 L/h for 3 s |
| Fan with vents open | Fans permitted only with the vents' closed limit made; vent opening blocked while a fan is commanded |
| Reversing contactors | Mechanical and electrical interlock; hardwired end limits break the coil circuit |
| Fog pump | Inlet pressure switch in the contactor coil circuit; RH ≥ 90 % blocks fog |
| Comms loss | OpenPLC sets the remote inputs to zero on a lost link: the fail-safe inputs read as *E-stop, dry, low, rain*, so everything trips. The I/O coupler drops its outputs after 1 s without a write |

**Fail-safe wiring.** Every protection-relevant input is closed when healthy, so a broken wire gives the safe interpretation [3].

## 6. Verification method

### 6.1 Running the real file

The Structured Text interpreter from T-101 parses `plc/greenhouse.st` and compiles it into Python closures [21]. In its **strict** mode it checks IEC types at run time, as strictly as the MatIEC compiler. A new **lean** mode skips those checks and runs about 1.6 times faster, with identical results (verified by a parity test). The automated tests run on the lean interpreter, and CI runs them again on the strict one [4].

### 6.2 A plant that pushes back

The plant model is written for this project:
- **Greenhouse air:** heat and water-vapour balances with ventilation that depends on vent opening, wind and buoyancy.
- **Crop:** transpiration driven by absorbed radiation.
- **Pads:** cooling down to the wet-bulb temperature (Stull's approximation [13]).
- **Hydraulics:** a pump curve against pressure-compensated drippers.
- **Water chemistry:** EC by mixing, and pH from a carbonate titration with the acid dose, through a mixing chamber and pipe dead time.
- **Weather:** deterministic clear, cloudy, rain and storm days.

48 faults can be injected: wire breaks, motor trips, jammed drives, a burst pipe, clogged zones, empty tanks, and six subtle faults that raise no alarm at all (section 8).

### 6.3 Fast-forward without cheating

The first scope draft accelerated only the plant. That idea was rejected: PLC timers, radiation sums and control loops would all have been wrong [2]. Instead the interpreter and the plant advance together in virtual time, 50 ms per scan. At 20 times real time a full day takes 72 minutes, and every timer behaves as it would at 1× [3]. The HMI derives process time from the PLC's scan counter, so its trends are also correct in fast-forward.

### 6.4 Four levels of testing

1. **Automated FAT on the bench** (`pytest`): plant and interpreter in one process, deterministic virtual time [4].
2. **Over TCP**: soft-PLC, plant and HMI over real Modbus TCP sockets, including a check against a third-party Modbus library.
3. **On the real toolchain**: STruC++ compile check in CI; FAT part B on OpenPLC Runtime v4, driven only through the runtime's Modbus server [5].
4. **Documents as tests**: the drawing generator checks that the drawn I/O matches `farmsim/tags.py`, every cross-reference resolves and every terminal appears in the terminal plan; generated documents must be up to date [4, 8].

## 7. Results

### 7.1 Acceptance tests

| Area | Tests | Covers |
|---|---|---|
| Irrigation | 17 | IRR-01…17: starts, sequence, metering, pause/resume, refill, set point clamps, clock fault |
| Fertigation | 8 | Feedforward, trim, band, HOLD, 1oo2 pH, crop protection |
| Climate | 12 | Vent demand, positioner, rain/wind/storm, shade net, fog, cooling sequence, fan staging |
| Safety and protection | 18 | SAF-01…16 |
| Diagnostics | 8 | Zone flow, drain %, counters, stack light |
| HMI | 8 | HMI-01…08: commands, set points, manual, alarms, trends, watchdog, simulation panel |
| Faults and trainer | 9 | Knowledge base, guide, subtle faults, challenge flow |
| Communications, OpenPLC project, drawings | 14 | Modbus, comms loss, fast-forward, generated Editor project, drawing consistency |
| Full day | 1 | NFR-09 climate performance, all cycles in band (slow test) |
| Interpreter | 19 | Language runtime, strictness, lean parity |

On 19 Nov 2026 the lean interpreter passed 112 with 2 skipped by design: the full day, which needs `--runslow`, and the pymodbus interoperability test, because pymodbus is not installed locally. The strict interpreter with `--runslow` passed 113, including the full day, in 33 minutes; only the pymodbus test was skipped. In GitHub Actions the first run on 19 Nov 2026 passed all five jobs: the FAT on Ubuntu and Windows with Python 3.10 and 3.12, and the strict interpreter with the full day [4].

### 7.2 A simulated day

On the default clear day (05:00–19:00, 33 °C at 14:00):

| Measure | Result | Requirement |
|---|---|---|
| Greenhouse maximum | 32.4 °C | ≤ 35 °C |
| Cooling switches | one VENT → COOL → VENT round trip (11:07–18:23) | ≤ 4 per day |
| Irrigation | 18 cycles, first at 06:30, 4.4 m³ | all complete |
| Drain | 43.8 % | 10–50 % |
| EC / pH while watering | 2.48–2.50 mS/cm / 5.79–5.82 | SP 2.5 ± 0.2 / 5.8 ± 0.3 |
| Time to band in PRE-MIX | about 32 s | ≤ 180 s (A10) |
| Alarms | none | none |

### 7.3 Design errors the simulation caught

These were found before any hardware existed:
- **The first pump choice was wrong.** A 4 m³/h pump pushed a single zone to 5.3 bar against pressure-compensated drippers, so normal watering would have tripped the high-pressure alarm. The pump was resized to 1.5 m³/h at 3.2 bar, and the trip set at 3.9 bar, above the 3.8 bar of a fully clogged zone.
- **pH dipped to 4.5 at pump start.** The acid feedforward acted on a flow reading that was still rising. Three changes fixed it:
  - dosing waits for 3 s of stable flow;
  - the model gained its mixing chamber;
  - the PI loops gained the integration zone.
- **The drain alarm fired by 10:00.** With a 100 J/cm² threshold the crop was over-watered, because the radiation sensor is outside and the shade net halves what the crop receives. The threshold became 130 J/cm².
- **A step-timeout alarm fired the moment PRE-MIX began,** from a timer value left over from the previous step. Timers now only count after one scan in the step.
- **The HMI froze in fast-forward.** The fast-forward runner held the Modbus image lock for a whole batch of scans, so HMI requests timed out. It now copies values in and out under the lock and keeps HMI writes that arrive mid-batch. A test covers it.

### 7.4 On OpenPLC Runtime v4

FAT part B ran on OpenPLC Runtime v4.3.2 in Docker on WSL2. The program was uploaded with the Editor's command-line tool from a project generated from the `.st` file [5]:

| Test | Result |
|---|---|
| Load, heartbeat, register map | 20.0 scans/s, `%MW139` backed (256-word `%MW` table), coupler watchdog quiet |
| Irrigation cycle, 4 × 10 L | 168 s, in band after 43 s, \|EC − SP\| ≤ 0.14, \|pH − SP\| ≤ 0.12, 45 L, no alarms |
| E-stop during a shot | Field outputs off 98 ms after the input opened (includes the 50 ms remote-I/O read and write) |
| EC analyser wire break | A23 and trip after 1.11 s; acid and A/B dosing stopped |
| Vent positioner | 37 % reached within 0.4 % over the real remote-I/O cycle |
| Set point clamps | Values clamped and read back |
| Remote I/O lost during a shot | Trip with A00 after 0.06 s; clean RESET once the link returned |

The same script gives 7 of 7 against the soft-PLC. Only the E-stop time differs (36 ms), because the soft-PLC polls its I/O every scan.

## 8. The field side: drawings, commissioning and fault finding

**Electrical drawing set.** 15 A3 sheets, generated from one data model by a script that reuses the T-101 drawing engine [8, 21]:
- power distribution;
- pump, fan, drive and dosing feeders;
- the safety circuit;
- one sheet each for digital inputs, digital outputs and analog loops;
- terminal plans, cables, panel layout, parts list and network.

**Generated from the same data**, so the four cannot disagree:
- terminal numbers;
- wire numbers;
- the parts list;
- the **I/O checkout sheet** with a test method for each of the 65 channels [9].

**Commissioning procedure** in ten phases [6], from dead checks to a three-day Site Acceptance Test. It includes the greenhouse-specific steps:
- zone reference flows from a bucket test;
- dripper uniformity;
- ZT-511 calibration at the end limits;
- a measurement of the water's alkalinity on site to set the acid feedforward.

**Troubleshooting.** A knowledge base describes each of the 48 faults: symptoms, how to confirm it, root cause and fix. It generates the troubleshooting guide [7] and drives a challenge in the HMI: the simulator hides a random fault, the trainee runs the plant, may take one "field check", and names the fault. Six faults are deliberately subtle and raise no alarm:
- an EC analyser that reads 0.4 mS/cm high, so the crop gets 2.1 instead of 2.5;
- a flowmeter that reads 20 % high;
- a return valve passing water;
- a partly clogged zone just inside the alarm limit;
- a weak stock tank;
- a greenhouse temperature sensor that reads 3 °C low.

They teach the hardest troubleshooting lesson: a perfect HMI and no alarm do not mean a healthy plant. Two of them, the high flowmeter and the passing valve, give the same symptom on the HMI. Only a field check with a clamp-on meter separates them.

## 9. Limitations: what has not been proven

- **No physical hardware.** The program has run on the real OpenPLC runtime, but against a simulated plant. Wiring, sensor noise, contact bounce, EMC and real network behaviour are untested.
- **The plant model is simplified:**
  - one well-mixed air volume;
  - no crop growth or substrate model beyond a water balance;
  - ideal pressure-compensated drippers;
  - deterministic weather.

  In the model, wet pads lower the house temperature only slightly compared with ventilation. Even nearly dry pads change the afternoon average by about 0.2 °C, so the model probably underestimates evaporative cooling. Its cooling results should be read as control-logic tests, not as a design of the cooling capacity.
- **Safety.** The performance level of the E-stop function has not been verified with component data. The final elements are single contactors, which limits it to about PL c. The protection functions are deliberately PLC functions, not safety functions.
- **Not tried on Runtime v4:**
  - persistent (RETAIN) set points;
  - the Editor's live debugger on GH-1 (it was checked on T-101).

  After a power cut, the set points return to their defaults [3].
- **Security.** Modbus TCP has no authentication. The design relies on network separation (drawing E-14). The HMI has no login.
- **Tuning.** The dosing gains were tuned against the model. They must be re-checked on site with the measured water analysis and pump capacities (commissioning phase 8).

## 10. Roadmap

1. **Hardware in the loop.** A Raspberry Pi with industrial I/O, or a Modbus TCP coupler, wired to switches, lamps and a 4–20 mA calibrator in place of the plant. Then the commissioning procedure, run for real.
2. **A vendor port.** The same functions in Siemens SCL or CODESYS, to show the design is not tied to OpenPLC.
3. **A better climate model.** Two air zones, a crop transpiration model fitted to published data, and measured weather files instead of synthetic days.
4. **Operations.** A historian (MQTT or InfluxDB), alarm notification to a phone (FDS open item 3), RETAIN set points, and an HMI login.

## 11. Conclusion

GH-1 shows that the verification method of the T-101 project scales to a larger, continuous, weather-driven process:
- **traceable requirements:** every requirement has an automated test;
- **a plant model that pushes back:** off-design and fault-injected, so the trim loops and protections have real work to do;
- **the real file on the real toolchain.**

The simulation found four design errors that would otherwise have surfaced on site: an oversized pump, an acid dip at start-up, over-watering from an outside radiation sensor, and a false timeout. It also found an HMI concurrency bug. The program has passed its acceptance tests on OpenPLC Runtime v4.

**What remains** is the part that needs a real greenhouse: wiring, calibration and a crop.

## References

1. IEC 61131-3:2013, *Programmable controllers — Part 3: Programming languages*.
2. GH-1 scope record and Product Requirements Document: [SCOPE.md](SCOPE.md), [PRD.md](PRD.md).
3. GH-1 Functional Design Specification: [FDS.md](FDS.md).
4. Automated FAT: `tests/` and the GitHub Actions workflow `.github/workflows/ci.yml`.
5. OpenPLC deployment and FAT part B: [openplc.md](openplc.md) and [fat_partb_2026-11-19.json](fat_partb_2026-11-19.json).
6. Commissioning procedure: [COMMISSIONING.md](COMMISSIONING.md).
7. Troubleshooting and maintenance guide: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
8. Electrical drawing set: [drawings/README.md](drawings/README.md).
9. I/O checkout and loop check: [IO_CHECKOUT.md](IO_CHECKOUT.md).
10. Autonomy Logic, STruC++ 0.8.0, the OpenPLC v4 Structured Text compiler: <https://github.com/Autonomy-Logic/STruCpp>.
11. Autonomy Logic, OpenPLC Runtime v4 and OpenPLC Editor v4: <https://github.com/Autonomy-Logic/openplc-runtime>.
12. Allen, R. G., Pereira, L. S., Raes, D., Smith, M. (1998). *Crop evapotranspiration*. FAO Irrigation and Drainage Paper 56.
13. Stull, R. (2011). Wet-bulb temperature from relative humidity and air temperature. *Journal of Applied Meteorology and Climatology* 50, 2267–2269.
14. NAMUR NE 43, *Standardization of the signal level for the failure information of digital transmitters*.
15. ANSI/ISA-101.01, *Human Machine Interfaces for Process Automation Systems*.
16. ANSI/ISA-5.1, *Instrumentation Symbols and Identification*.
17. IEC 60204-1, *Safety of machinery — Electrical equipment of machines — Part 1: General requirements*.
18. ISO 13849-1, *Safety of machinery — Safety-related parts of control systems — Part 1: General principles for design*.
19. IEC 81346-2, *Industrial systems, installations and equipment and industrial products — Structuring principles and reference designations — Part 2: Classification of objects and codes for classes*.
20. ANSI/ASABE EP406, *Heating, Ventilating and Cooling Greenhouses*.
21. T-101 Batch Mixing Station (plc-batch-station), the first project of this series: <https://github.com/rayangmendrofa/plc-batch-station>.
