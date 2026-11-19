# Functional Design Specification — GH-1 Tropical Greenhouse

| | |
|---|---|
| **Document** | FDS-GH1, revision A |
| **Implements** | [PRD-GH1](PRD.md) |
| **Code** | `plc/greenhouse.st` (OpenPLC v4: STruC++ compiler, Runtime v4; IEC 61131-3 ST, task 50 ms) |
| **Verified by** | Automated FAT in `tests/` (phase 2); FAT document and OpenPLC part B in phase 4 |
| **Revision A** | Phase 2 results: pump re-sized (§3.2), A05 at 3.9 bar, dosing tuned with an integration zone and a 3 s flow permissive (§7), STOP in RUN-DOWN ends the cycle (§5.2), A07/A08 on flowing water only (§7.3), radiation sum default 130 J/cm² (§5.4) |

## 1. Purpose
This document defines *how* the control system meets the PRD: I/O, modes, time base, irrigation sequence, fertigation loops, climate state machine, interlocks, alarms, sensor fallbacks and the HMI register map. The PLC program implements exactly this document, and its comments reference these section numbers.

## 2. References
- IEC 61131-3: PLC programming languages
- ISA-5.1: instrumentation symbols and identification
- ISA-101: HMI design
- NAMUR NE 43: signal levels for failure information of 4–20 mA transmitters
- ANSI/ASABE EP406: heating, ventilating and cooling greenhouses (fan capacity, pad sizing)
- FAO Irrigation and Drainage Paper 56: saturation vapour pressure equation (used for VPD)
- OpenPLC v4: STruC++ compiler, Runtime v4 Modbus server and Modbus master (address map unchanged from v3)

## 3. Process description

### 3.1 Overview
```
 well/mains ──┬── XV-201 ──► T-201 5 m³ (LT-201, LSL-201)
              │                 │
              │                 ▼
              │               P-201 ─► FT-201 ─► injection: P-311 A, P-312 B, P-313 acid ─► static mixer
              │                                                                              │
              │                       AIT-301 EC, AIT-302/303 pH, PT-201 ◄────────────────────┘
              │                                     │
              │                ┌────────────────────┼──────────┬──────────┬──────────┐
              │             XV-301 (return)       XV-401     XV-402     XV-403     XV-404
              │                └──► T-201           Z1 (FT-402 drain)  Z2         Z3         Z4
              │
              ├── filter ──► P-541 fog pump ─► fog nozzles (70 bar)
              └── float valve ──► pad sump (LSL-531) ─► P-531 ─► pads ◄── air ◄── F-601…603 exhaust fans
```
The return line takes out-of-band solution back to T-201. The return volume is small (≈ 50 L per pre-mix against a 5 m³ tank and ≈ 250 L used per cycle), so the tank EC rises only slightly, and the EC loop corrects for it. Because T-201 contains some nutrient, **fog and pad water come from the clean supply line, not from T-201** (nutrient spray clogs nozzles and leaves residue on leaves).

### 3.2 Design values
| Item | Value |
|---|---|
| Greenhouse | 40 × 25 m = 1 000 m², gutter 4.5 m, ridge 6 m, ≈ 5 250 m³; UV-stabilised PE film, transmissivity 0.70 |
| Roof vent | Continuous ridge vent, opening area 20 % of floor at 100 %, insect net; full stroke 120 s |
| Shade net | External, 50 % shading, full stroke 90 s |
| Pad-and-fan | Cellulose pad 25 × 1.5 m × 150 mm on the north gable, saturation efficiency 0.80; 3 exhaust fans × 48 000 m³/h on the south gable (≈ 144 m³/h per m² floor, per ASABE EP406) |
| Fog | High-pressure 70 bar, 100 nozzles × 5 L/h = 500 L/h |
| Zones Z1–Z4 | 250 m² each, 625 pressure-compensated drippers × 2 L/h = 1 250 L/h, 1.5–2.5 bar |
| T-201 / refill | 5 m³ / 3 m³/h from well or mains, overflow pipe at 98 % |
| P-201 | 1.5 m³/h at 3.2 bar, shut-off head 4.0 bar (one zone: 1.25 m³/h at 3.4 bar). *Rev. A: the first choice (4 m³/h, 5.5 bar shut-off) pushed the pressure-compensated drippers to 5.3 bar on a single zone.* |
| Return XV-301 | ≈ 1 500 L/h at 3 bar |
| Stock A / B | 200 L each, 1 : 100 concentrate (A + B at 1 % each add ≈ 2.0 mS/cm) |
| Acid | 100 L, 10 % nitric acid |
| Dosing pumps | P-311 / P-312: 0–40 L/h; P-313: 0–10 L/h; speed reference 0–100 % |
| Raw water | EC 0.3 mS/cm, pH 7.4, design alkalinity 3.0 mmol/L HCO₃⁻ (nonlinear titration curve). The simulation deliberately runs at 3.4 mmol/L with stock mixed 10 % strong, so the feedforward is off and the PI trim has to correct it (§7.1) |
| Mixing and dead time | 3 L mixing chamber after the injection point (τ ≈ 9 s at 1 250 L/h), then 1.4 L of pipe to the sensors (≈ 4 s), sensor lag ≈ 3 s |
| Climate (default clear day) | Sunrise 06:00, sunset 18:00 (WIB, no daylight saving); radiation peak 900 W/m²; outside 24 °C at 06:00 to 33 °C at 14:00; RH 95 % → 55 %; wind 1–4 m/s |

## 4. I/O list

Field I/O is on a Modbus TCP remote-I/O device, configured in OpenPLC as remote device **PLANT**. I/O groups: DI function code 2, length 32; IR function code 4, length 16; coils function code 15, length 24; holding registers function code 16, length 3. Read groups use error handling **Set to zero** (§13).

### 4.1 Digital inputs (25 used, 7 spare)
| PLC address | Dev. | Tag | Description | Contact | 1 = |
|---|---|---|---|---|---|
| `%IX100.0` | DI 0 | `ESTOP_OK` | E-stop safety relay healthy (monitoring) | relay NO, closed when healthy | healthy |
| `%IX100.1` | DI 1 | `PB_START` | Panel START | NO | pressed |
| `%IX100.2` | DI 2 | `PB_STOP_OK` | Panel STOP | NC | not pressed |
| `%IX100.3` | DI 3 | `PB_RESET` | Panel RESET | NO | pressed |
| `%IX100.4` | DI 4 | `LSL201_OK` | LSL-201 T-201 low level | closed when wet | water present |
| `%IX100.5` | DI 5 | `P201_FB` | P-201 running (contactor aux in series with breaker aux) | NO | running |
| `%IX100.6` | DI 6 | `LSL311_OK` | LSL-311 stock A low level | closed when wet | not low |
| `%IX100.7` | DI 7 | `LSL312_OK` | LSL-312 stock B low level | closed when wet | not low |
| `%IX101.0` | DI 8 | `LSL313_OK` | LSL-313 acid low level | closed when wet | not low |
| `%IX101.1` | DI 9 | `P311_FB` | P-311 running (pump run relay) | NO | running |
| `%IX101.2` | DI 10 | `P312_FB` | P-312 running | NO | running |
| `%IX101.3` | DI 11 | `P313_FB` | P-313 running | NO | running |
| `%IX101.4` | DI 12 | `RAIN_DRY` | XS-105 rain detector | NC, opens on rain | no rain |
| `%IX101.5` | DI 13 | `ZSO511` | Vent fully open (aux contact of the hardwired end limit) | NO | at limit |
| `%IX101.6` | DI 14 | `ZSC511` | Vent fully closed | NO | at limit |
| `%IX101.7` | DI 15 | `M511_OK` | Vent motor breaker/overload healthy | NO, closed when healthy | healthy |
| `%IX102.0` | DI 16 | `ZSO521` | Shade net fully open (retracted) | NO | at limit |
| `%IX102.1` | DI 17 | `ZSC521` | Shade net fully closed (deployed) | NO | at limit |
| `%IX102.2` | DI 18 | `M521_OK` | Shade net motor breaker/overload healthy | NO, closed when healthy | healthy |
| `%IX102.3` | DI 19 | `F601_FB` | F-601 running | NO | running |
| `%IX102.4` | DI 20 | `F602_FB` | F-602 running | NO | running |
| `%IX102.5` | DI 21 | `F603_FB` | F-603 running | NO | running |
| `%IX102.6` | DI 22 | `P531_FB` | P-531 pad pump running | NO | running |
| `%IX102.7` | DI 23 | `LSL531_OK` | LSL-531 pad sump low level | closed when wet | water present |
| `%IX103.0` | DI 24 | `P541_FB` | P-541 fog pump running (pump stops itself on low inlet pressure) | NO | running |

Every safety- or protection-relevant input is fail-safe: a broken wire reads 0 and gives the safe interpretation (E-stop, dry, low, rain, motor fault).

### 4.2 Analog inputs (0–65535 = 0–20 mA; 4 mA = 13107; fault < 3.6 mA = raw ≤ 11796)
| PLC address | Dev. | Tag | Range (4–20 mA) | Fallback on signal fault (§12.2) |
|---|---|---|---|---|
| `%IW100` | IR 0 | `LT201_RAW` | 0–100 % | Refill blocked |
| `%IW101` | IR 1 | `FT201_RAW` | 0–6 000 L/h | Irrigation trips |
| `%IW102` | IR 2 | `PT201_RAW` | 0–6.0 bar | Irrigation trips |
| `%IW103` | IR 3 | `AIT301_RAW` | 0–5.0 mS/cm | Irrigation trips |
| `%IW104` | IR 4 | `AIT302_RAW` | 0–14 pH | Use AIT-303 |
| `%IW105` | IR 5 | `AIT303_RAW` | 0–14 pH | Use AIT-302 |
| `%IW106` | IR 6 | `FT402_RAW` | 0–200 L/h | Drain % frozen |
| `%IW107` | IR 7 | `RT101_RAW` | 0–1 500 W/m² | Radiation sum frozen; shade net on temperature only |
| `%IW108` | IR 8 | `TT101_RAW` | 0–50 °C | Display only |
| `%IW109` | IR 9 | `MT101_RAW` | 0–100 % | Display only |
| `%IW110` | IR 10 | `ST101_RAW` | 0–40 m/s | Treated as storm |
| `%IW111` | IR 11 | `TT501_RAW` | 0–50 °C | Vent fixed 50 %, COOL and fog blocked |
| `%IW112` | IR 12 | `MT501_RAW` | 0–100 % | Humidity venting and fog off |
| `%IW113` | IR 13 | `AT502_RAW` | 0–2 000 ppm | Display only |
| `%IW114` | IR 14 | `ZT511_RAW` | 0–100 % | Vent on limit switches only |
| `%IW115` | IR 15 | `CLOCK_MIN` | **Not 4–20 mA**: minutes since midnight, 0–1439, from the I/O clock module | Daylight test replaces the day window (§5.3) |

### 4.3 Digital outputs (22 used, 2 spare)
| PLC address | Dev. | Tag | Description | De-energised |
|---|---|---|---|---|
| `%QX100.0` | coil 0 | `XV201` | Refill valve | closed (NC solenoid) |
| `%QX100.1` | coil 1 | `P201` | Main pump contactor | stopped |
| `%QX100.2` | coil 2 | `XV301` | Return valve | closed |
| `%QX100.3` … `.6` | coil 3–6 | `XV401` … `XV404` | Zone valves Z1–Z4 | closed |
| `%QX100.7` | coil 7 | `P311` | Dosing pump A run | stopped |
| `%QX101.0` | coil 8 | `P312` | Dosing pump B run | stopped |
| `%QX101.1` | coil 9 | `P313` | Acid pump run | stopped |
| `%QX101.2` | coil 10 | `M511_OPEN` | Vent motor, open contactor | stopped (vent holds position) |
| `%QX101.3` | coil 11 | `M511_CLOSE` | Vent motor, close contactor | stopped |
| `%QX101.4` | coil 12 | `M521_OPEN` | Shade net motor, retract contactor | stopped (net holds position) |
| `%QX101.5` | coil 13 | `M521_CLOSE` | Shade net motor, deploy contactor | stopped |
| `%QX101.6` … `%QX102.0` | coil 14–16 | `F601` … `F603` | Exhaust fan contactors | stopped |
| `%QX102.1` | coil 17 | `P531` | Pad pump contactor | stopped |
| `%QX102.2` | coil 18 | `P541` | Fog pump contactor | stopped |
| `%QX102.3` | coil 19 | `LAMP_GREEN` | Stack light green | off |
| `%QX102.4` | coil 20 | `LAMP_AMBER` | Stack light amber | off |
| `%QX102.5` | coil 21 | `LAMP_RED` | Stack light red | off |

The open/close contactors of each reversing motor are also interlocked electrically (NC aux of each in the other's coil circuit), and the end limits break the coil circuit directly.

### 4.4 Analog outputs (0–65535 = 0–100 %)
| PLC address | Dev. | Tag | Use |
|---|---|---|---|
| `%QW100` | HR 0 | `P311_REF` | Dosing pump A speed |
| `%QW101` | HR 1 | `P312_REF` | Dosing pump B speed |
| `%QW102` | HR 2 | `P313_REF` | Acid pump speed |

## 5. Control philosophy

### 5.1 Subsystems and modes
The program has two subsystems with their own modes. Interlocks (§11) apply in every mode.

| Subsystem | Mode | Entered | Behaviour |
|---|---|---|---|
| Irrigation + fertigation | AUTO | Power-up default; HMI command from MANUAL | Sequence (§6) and dosing loops (§7) drive the requests |
| | MANUAL | HMI command, **only in IDLE (0) or FAULT (99)**; step set to 0 | Each device requested from HMI bits; dosing speeds from HMI. Leaving MANUAL clears the requests |
| Climate | AUTO | Power-up default; HMI command from MANUAL | State machine (§8) drives the requests |
| | MANUAL | HMI command, **at any time** | Vent position, net, fans, pad and fog from HMI. Leaving MANUAL clears the requests and enters VENT (10) |

At power-up the irrigation program is **enabled** (`IRR_ENABLE_AT_START = TRUE`), so the crop is watered after a power cut once the E-stop relay is reset (open item §14-3).

### 5.2 Commands
| Command | Source | Effect |
|---|---|---|
| START | Panel PB (rising edge) or HMI b0 | Irrigation AUTO: IDLE → program enabled; PAUSED → resume (§6.2). Inhibited while STOP is held |
| STOP | Panel PB (falling edge of NC) or HMI b1 | PRE-MIX, SHOT, HOLD (10–25) → PAUSED; RUN-DOWN (40) → IDLE (all zones already watered); IDLE → program disabled |
| RESET | Panel PB (rising edge) or HMI b2 | Clears latched alarms whose condition has gone, device lockouts and the zone diagnostic word |
| IRRIGATE NOW | HMI b3 | Irrigation AUTO, IDLE → start one cycle (§6.1) |
| ABORT | HMI b4 | PAUSED → IDLE, cycle cancelled |
| IRR AUTO / IRR MANUAL | HMI b5 / b6 | §5.1 |
| CLIM AUTO / CLIM MANUAL | HMI b7 / b8 | §5.1 |

### 5.3 Time base and time of day
- **Process time base.** A 1 s tick is made by counting scans (`SCANS_PER_S = 20` at the 50 ms task). Unlike a self-resetting TON, it loses no time, so all seconds and minutes counters are accurate to the task timing (PRD NFR-04). Volumes integrate flow every scan with `DT_SCAN = 0.05 s`. *Constraint:* the constants must change if the task interval changes (§14-6).
- **Time of day.** Portable ST has no real-time clock, so the I/O clock module publishes minutes since midnight in `CLOCK_MIN`. Indonesia (WIB) has no daylight saving.
- **Clock fault** (A01): `CLOCK_MIN` > 1439, or unchanged for 150 s. The day window is then replaced by *daylight*: RT-101 ≥ 50 W/m² for 5 min. If RT-101 has also failed, the window is treated as open: watering at night is a smaller risk than not watering.
- **Midnight**: when `CLOCK_MIN` goes from ≥ 1430 to < 10 (clock healthy), daily counters roll over (§6.5).
- **Fast-forward demo.** The PLC VM and the plant advance together in virtual time (same 50 ms scan), so behaviour at 20× is identical to 1×. The PLC program has no knowledge of the speed.

### 5.4 Setpoints
Written by the HMI, checked by the PLC every scan, clamped and written back (PRD FR-13). Default values are loaded at cold start.

| Register | Tag | Unit | Default | Limits |
|---|---|---|---|---|
| `%MW10` | `SP_EC` | 0.01 mS/cm | 250 | 50 – 400 |
| `%MW11` | `SP_PH` | 0.01 pH | 580 | 500 – 680 |
| `%MW12` | `SP_EC_BAND` | 0.01 mS/cm | 20 | 10 – 50 |
| `%MW13` | `SP_PH_BAND` | 0.01 pH | 30 | 10 – 50 |
| `%MW14` | `SP_DAY_START` | min of day | 390 (06:30) | 0 – 1380 |
| `%MW15` | `SP_DAY_END` | min of day | 1020 (17:00) | `SP_DAY_START` + 30 – 1439 |
| `%MW16` | `SP_RAD_SUM` | J/cm² (outside radiation) | 130 | 30 – 300 |
| `%MW17` | `SP_MIN_INT` | min | 20 | 5 – 240 |
| `%MW18` | `SP_MAX_INT` | min | 120 | `SP_MIN_INT` – 480 |
| `%MW19` | `SP_MAX_CYCLES` | cycles/day | 30 | 1 – 60 |
| `%MW20–23` | `SP_SHOT_Z1…Z4` | L | 60 | 10 – 300 |
| `%MW24–27` | `SP_FLOW_Z1…Z4` | L/h (reference flow) | 1250 | 200 – 3000 |
| `%MW28` | `SP_ZONE_EN` | b0–b3 = Z1–Z4 enabled | 15 | 0 – 15 |
| `%MW30` | `SP_VENT_T` | 0.1 °C | 280 | 200 – 350 |
| `%MW31` | `SP_COOL_T` | 0.1 °C | 320 | `SP_VENT_T` + 10 – 400 |
| `%MW32` | `SP_RH_MAX` | 0.1 % | 850 | 600 – 950 |
| `%MW33` | `SP_VPD_FOG` | 0.01 kPa | 160 | 80 – 250 |
| `%MW34` | `SP_SCREEN_RAD` | W/m² | 650 | 300 – 1000 |
| `%MW35` | `SP_WIND_LIM` | 0.1 m/s | 100 | 50 – 200 |
| `%MW36` | `SP_STORM` | 0.1 m/s | 150 | `SP_WIND_LIM` + 10 – 250 |
| `%MW37` | `SP_RAIN_POS` | 0.1 % | 100 | 0 – 300 |

Changes take effect at once, except shot volume and reference flow, which are read when a zone's shot starts.

## 6. Irrigation

### 6.1 Cycle start
Evaluated in AUTO, step 0, every scan:

```
in_window := clock healthy  ? SP_DAY_START <= CLOCK_MIN < SP_DAY_END
           : RT-101 healthy ? daylight (RT-101 >= 50 W/m2 for 5 min)
           : TRUE
auto_start := irr_enabled AND in_window AND cycles_day < SP_MAX_CYCLES
              AND ( (rad_sum >= SP_RAD_SUM AND min_since >= SP_MIN_INT) OR min_since >= SP_MAX_INT )
start := auto_start OR IRRIGATE_NOW
```
At start: `rad_sum := 0`, `min_since := 0`, `cycles_day := cycles_day + 1`, zone pointer to the first enabled zone. If no zone is enabled, the cycle is not started.

- `rad_sum` (J/cm²) adds `RT-101 [W/m²] / 10 000` every second while RT-101 is healthy (frozen otherwise).
- `min_since` counts minutes from the last cycle start, saturating at 65 535. At cold start it is set to `SP_MAX_INT`, so the first cycle in the window starts at once (this is also the morning start shot, PRD FR-04).

### 6.2 Sequence
| Step | Name | Requests | Transition | Supervision |
|---|---|---|---|---|
| 0 | IDLE | — | start (§6.1) → 10 | — |
| 10 | PRE-MIX | P-201, XV-301, dosing | EC and pH in band for 10 s → 20 | A10 at 180 s |
| 20 | SHOT | P-201, dosing, zone valve *n*; XV-301 for the first 2 s (overlap) | zone volume ≥ shot → next enabled zone (stay in 20, open-before-close, 2 s overlap) or, after the last zone, → 40. Out of band for 10 s → 25 | Shot timeout (§6.3) → skip zone |
| 25 | HOLD | P-201, XV-301, dosing; zone valve *n* for the first 2 s | in band for 10 s → 20 (same zone, volume kept) | A10 at 180 s |
| 40 | RUN-DOWN | t = 0: dosing off, XV-301 open; t = 2 s zone valve closed; t = 5 s P-201 off; t = 6 s → 0 | → 0 | — |
| 80 | PAUSED | — (irrigation outputs off) | START → 10, then the interrupted zone gets its remaining volume. ABORT → 0 | — |
| 99 | FAULT | — (irrigation outputs off) | no irrigation trip alarm latched → 0; the cycle is discarded | — |

Evaluated each scan before the step logic (AUTO only): (1) any latched alarm in `TRIP_IRR` → 99; (2) STOP in steps 10–25 → keep the zone and its volume, go to 80; STOP in 40 → 0. The step timer restarts on every step change.

*In band* means |EC − `SP_EC`| ≤ `SP_EC_BAND` **and** |pH − `SP_PH`| ≤ `SP_PH_BAND`, with EC healthy and pH valid (§7.4).

### 6.3 Zone metering and diagnostics
- **Zone volume** integrates FT-201 while the zone's valve is commanded and XV-301 is closed (no overlap). During changeover both zones share the flow; the 2 s overlap volume (≈ 1.4 L) is not counted, which errs on the side of a slightly larger shot.
- **Shot timeout**: `t_max = 2 × SP_SHOT / SP_FLOW × 3600 s + 30 s`. On timeout the zone is skipped, A19 is raised and the zone's timeout bit is set in `ST_ZONE_DIAG`.
- **Flow deviation**: checked once the valve has been open 20 s with no overlap. FT-201 > 1.25 × `SP_FLOW` for 20 s → A17 (leak, broken dripper); < 0.75 × `SP_FLOW` for 20 s → A18 (clogged drippers, valve not opening). Both are warnings; the shot continues (volume-metered).
- `ST_ZONE_DIAG`: b0–b3 flow high Z1–Z4, b4–b7 flow low, b8–b11 shot timeout. Cleared by RESET.

### 6.4 Tank refill
XV-201 is requested when LT-201 < 40 % and released at ≥ 85 % (both modes respect the 95 % interlock). Refill failure (A03, warning): XV-201 open 600 s with a level rise below 2 %. LSL-201 is an independent switch, so a failed LT-201 cannot cause a dry-running pump.

### 6.5 Daily counters and drain
| Counter | Source | Rollover at midnight |
|---|---|---|
| `cycles_day` | cycle starts | → `cycles_prev`, reset |
| `water_day` (L) | FT-201 integrated while any zone valve is open | → `water_prev`, reset |
| `drain_day` (%) | FT-402 integrated (L) / Z1 supply integrated (L) × 100 | → `drain_prev`, reset with both integrals |

Drain alarm A28 (warning): evaluated at each cycle end after ≥ 5 cycles in the day; `drain_day` outside 10–50 %.

## 7. Fertigation

### 7.1 Structure
Both loops are *ratio control with feedback trim*: a feedforward term proportional to the measured water flow does most of the work, and a PI trim corrects the remaining error. This copes with the dead time (≈ 7 s) far better than PI alone, because a flow change (zone changeover, return valve) is corrected at once instead of after the dead time.

`FB_PIControl` from the template gains a feedforward input, a direction flag and an **integration zone**: `out = LIMIT(0, FF + Kp·(e + ∫e dt / Ti), 100)`, conditional-integration anti-windup, sample time 0.5 s, and the integral only runs while |e| < `I_ZONE`. Without the zone, a gain high enough for the small process gain (≈ 0.057 mS/cm per % at 1 500 L/h) wound the integral up during the ≈ 15 s of dead time and lag after start-up, and EC overshot to 2.95 mS/cm. Disabling the loop resets the integral and the output.

| Item | EC loop | pH loop |
|---|---|---|
| PV | AIT-301 | validated pH (§7.4) |
| SP | `SP_EC` | `SP_PH` |
| Direction | direct: e = SP − PV | reverse: e = PV − SP (acid lowers pH) |
| Feedforward | `(SP_EC − EC_BASE) × FT-201 [L/h] / FF_EC_DIV` | `FF_ACID × FT-201 [m³/h]` |
| Output | P-311 **and** P-312 speed (1 : 1) | P-313 speed |
| Tuning (phase 2) | Kp 8 %/(mS/cm), Ti 12 s, `I_ZONE` 0.5 mS/cm | Kp 5 %/pH, Ti 12 s, `I_ZONE` 0.5 |
| Result (simulated, off-design plant) | In band ≈ 32 s after PRE-MIX start; SHOT steady 2.48–2.50 mS/cm | SHOT steady 5.79–5.82 |

`EC_BASE` = 0.3 mS/cm and `FF_EC_DIV` = 80 follow from the design values: A + B at speed *s* % add 80 · *s* / *Q* mS/cm at flow *Q* L/h. `FF_ACID` = 13 %/(m³/h) neutralises the design alkalinity to pH ≈ 5.8; it is checked at commissioning. With feedforward only, the off-design plant settles at EC ≈ 2.75 and pH ≈ 6.0, outside the band, which is what the trim is for. Gains were tuned by sweeps against the simulated plant and must be re-checked on site.

### 7.2 Enable
A loop runs in AUTO when the step is 10, 20 or 25 **and** its interlock word is 0 (§11). In MANUAL the speeds come from `HMI_MAN_DOSE_*`, still subject to the interlocks. In AUTO the run outputs stay on for the whole pumping step; the speed may be 0. The flow permissive needs P-201 running with FT-201 ≥ 500 L/h **for 3 s**, so the flow used by the feedforward has settled before dosing starts (without it, pH dipped to 4.5 during pump start-up).

### 7.3 Crop-protection limits
| Alarm | Condition | Delay | Action |
|---|---|---|---|
| A07 EC high-high | EC ≥ `SP_EC` + 1.0 mS/cm (EC healthy, P-201 running) | 5 s | A/B dosing and zone valves blocked, irrigation trips |
| A08 pH low-low | pH ≤ 4.5 (pH valid, P-201 running) | 5 s | Acid dosing and zone valves blocked, irrigation trips |

Both are evaluated on flowing water only: standing water in the sensor line after a setpoint change is not a hazard and must not trip.

### 7.4 pH validation (1oo2 with fallback)
| AIT-302 | AIT-303 | pH used | `ph_valid` | Alarms |
|---|---|---|---|---|
| healthy | healthy | average | TRUE, unless the deviation alarm is active | A09 if \|A − B\| > 0.3 for 10 s (trip) |
| healthy | fault | AIT-302 | TRUE | A25 (warning) |
| fault | healthy | AIT-303 | TRUE | A24 (warning) |
| fault | fault | last value | FALSE | A24, A25, A26 (trip) |

Acid dosing requires `ph_valid` (§11).

## 8. Climate

### 8.1 States
| State | Name | Vent demand | Net | Fog | Pad pump | Fans | Transition |
|---|---|---|---|---|---|---|---|
| 10 | VENT | §8.2 | §8.5 | §8.6 | off | off | COOL condition (below) → 20 |
| 20 | COOL-START | 0 % | §8.5 | off | off | off | vents closed (ZSC-511, or ZT-511 ≤ 5 %) → 25 |
| 25 | PRE-WET | 0 % | §8.5 | off | on | off | 60 s → 30 |
| 30 | COOL | 0 % | §8.5 | off | on | staged §8.7 | T < `SP_COOL_T` − 3.0 °C for 10 min → 40 |
| 40 | PAD-DRY | 0 % | §8.5 | off | off | F-601 only | 5 min → 10 |
| 90 | MANUAL | HMI | HMI | HMI | HMI | HMI | CLIM AUTO → 10 |

- **COOL condition**: TT-501 healthy **and** T ≥ `SP_COOL_T` for 5 min **and** (vent demand ≥ 90 % **or** vents held back by rain, wind or storm).
- TT-501 fault in states 20–30 → 40 (dry the pads, then VENT with the fallback).
- E-stop: all outputs off (interlocks); the state is set to 10, so climate restarts in VENT after RESET.
- A fan lockout does not end COOL; the remaining fans carry the load. If no fan can run in COOL for 60 s → 40.

### 8.2 Vent demand (VENT state)
```
temp_dem := PI(TT-501, SP_VENT_T)            direct acting, 0–100 %, sample 5 s, Kp 15 %/°C, Ti 600 s
hum_dem  := LIMIT(0, (RH − SP_RH_MAX) × 5 %/%, 50)
demand   := MAX(temp_dem, hum_dem)
vent_sp  := MIN(demand, weather_max)
```
With TT-501 failed: `temp_dem := VENT_FALLBACK` (50 %). With MT-501 failed: `hum_dem := 0`.

### 8.3 Weather limits
| Condition | `weather_max` | Released |
|---|---|---|
| none | 100 % | — |
| rain (`RAIN_DRY` = 0) | `SP_RAIN_POS` | dry for 5 min |
| wind ≥ `SP_WIND_LIM` | 30 % (`VENT_WIND_MAX`) | wind < `SP_WIND_LIM` − 1.0 m/s for 5 min |
| wind ≥ `SP_STORM`, or ST-101 fault | 0 % and net retracted | wind < `SP_STORM` − 1.0 m/s for 5 min (sensor healthy) |

Limits apply at once on the instantaneous value and release only after the delay, so gusts don't make the vents hunt. When several apply, the lowest wins. Weather limits also cap the manual vent position (equipment protection).

### 8.4 Vent positioner (`FB_Actuator`, 3-point step)
- Drive open when `vent_sp − ZT-511` > 2 %, drive close when < −2 %; stop when the error is within ± 0.5 % or the end limit is made.
- 0.5 s pause when reversing; open and close are never commanded together.
- `vent_sp` = 0 % drives to ZSC-511 (closing continues until the limit, so the vent seals); 100 % drives to ZSO-511.
- ZT-511 fault: `vent_sp` ≥ 50 % → drive to ZSO-511, otherwise to ZSC-511.
- Travel fault A36: motor commanded and ZT-511 changes < 1 % in 15 s (ZT healthy), or the limit is not reached in 180 s (ZT fault). Locks out the vent until RESET.

### 8.5 Shade net
| Demand | Condition |
|---|---|
| Deploy (close) | RT-101 ≥ `SP_SCREEN_RAD` for 10 min, or T ≥ `SP_VENT_T` + 4.0 °C |
| Retract (open) | RT-101 < `SP_SCREEN_RAD` − 150 for 15 min and T < `SP_VENT_T` + 2.0 °C |
| Forced retract | storm, or ST-101 fault (external net) |

With RT-101 failed the net follows temperature only; with TT-501 failed, radiation only. The net drives until its limit (ZSC-521 / ZSO-521); A37 if the limit is not reached in 150 s.

### 8.6 Fogging (VENT state only)
`VPD = es(T) × (1 − RH/100)`, `es(T) = 0.6108 · EXP(17.27·T / (T + 237.3))` kPa (FAO-56).
Fog demand ON when VPD > `SP_VPD_FOG` and T > `SP_VENT_T`; OFF when VPD < `SP_VPD_FOG` − 0.30 kPa. While ON, P-541 pulses 10 s on / 50 s off (`FOG_ON`, `FOG_OFF`). Blocked without TT-501 or MT-501, in rain, and by the interlock (RH ≥ 90 %).

### 8.7 Fan staging (COOL state)
| Stage | Fans | Up when | Down when |
|---|---|---|---|
| 1 | F-601 | on entry to 30 | — |
| 2 | + F-602 | T ≥ `SP_COOL_T` − 1.0 °C for 60 s | T < `SP_COOL_T` − 1.5 °C for 120 s |
| 3 | + F-603 | T ≥ `SP_COOL_T` + 1.0 °C for 60 s | T < `SP_COOL_T` + 0.5 °C for 120 s |

A locked-out fan is replaced by the next available fan, so the number of running fans matches the stage where possible.

## 9. HMI interface

OpenPLC maps `%MWn` to holding register **1024 + n**. All values are 16-bit unsigned. Single source of truth in code: `farmsim/tags.py`.

### 9.1 HMI → PLC
| Address | Reg. | Tag | Content |
|---|---|---|---|
| `%MW0` | 1024 | `HMI_CMD` | b0 START, b1 STOP, b2 RESET, b3 IRRIGATE NOW, b4 ABORT, b5 IRR AUTO, b6 IRR MANUAL, b7 CLIM AUTO, b8 CLIM MANUAL. **One-shot: cleared by the PLC after reading** |
| `%MW1` | 1025 | `HMI_MAN_IRR` | b0 XV-201, b1 P-201, b2 XV-301, b3–b6 XV-401…404 |
| `%MW2–4` | 1026–1028 | `HMI_MAN_DOSE_A`, `_B`, `_ACID` | Manual dosing speed, 0.1 % |
| `%MW5` | 1029 | `HMI_MAN_CLIM` | b0 net deploy, b1 net retract, b2–b4 F-601…603, b5 P-531, b6 P-541 |
| `%MW6` | 1030 | `HMI_MAN_VENT` | Manual vent position, 0.1 % |
| `%MW10–37` | 1034–1061 | `SP_*` | Setpoints (§5.4) |

### 9.2 PLC → HMI
| Address | Reg. | Tag | Content |
|---|---|---|---|
| `%MW40` | 1064 | `ST_HEARTBEAT` | +1 per scan; HMI flags comms loss if unchanged for 2 s |
| `%MW41` | 1065 | `ST_CLOCK` | Time of day used, min |
| `%MW42` | 1066 | `ST_IRR_STEP` | §6.2 |
| `%MW43` | 1067 | `ST_IRR_FLAGS` | b0 AUTO, b1 MANUAL, b2 program enabled, b3 in window, b4 max cycles reached, b5 daylight fallback, b6 paused zone pending |
| `%MW44` | 1068 | `ST_ZONE` | Active zone 0–4 |
| `%MW45` | 1069 | `ST_ZONE_VOL` | Zone volume delivered, 0.1 L |
| `%MW46` | 1070 | `ST_STEP_TIME` | Time in step, s |
| `%MW47` | 1071 | `ST_RAD_SUM` | Radiation sum, 0.1 J/cm² |
| `%MW48` | 1072 | `ST_MIN_SINCE` | Minutes since last cycle start |
| `%MW49–51` | 1073–1075 | `ST_CYCLES_DAY`, `ST_WATER_DAY` (L), `ST_DRAIN_DAY` (0.1 %) | Today |
| `%MW52–54` | 1076–1078 | `ST_CYCLES_PREV`, `ST_WATER_PREV`, `ST_DRAIN_PREV` | Previous day |
| `%MW55` | 1079 | `ST_ZONE_DIAG` | §6.3 |
| `%MW56` | 1080 | `ST_LEVEL` | T-201 level, 0.1 % |
| `%MW57` | 1081 | `ST_FLOW` | FT-201, L/h |
| `%MW58` | 1082 | `ST_PRESS` | PT-201, 0.01 bar |
| `%MW59` | 1083 | `ST_EC` | 0.01 mS/cm |
| `%MW60–62` | 1084–1086 | `ST_PH`, `ST_PH_A`, `ST_PH_B` | pH used / AIT-302 / AIT-303, 0.01 |
| `%MW63–65` | 1087–1089 | `ST_DOSE_A`, `_B`, `_ACID` | Dosing outputs, 0.1 % |
| `%MW66` | 1090 | `ST_DRAIN_FLOW` | FT-402, 0.1 L/h |
| `%MW67` | 1091 | `ST_RAD` | RT-101, W/m² |
| `%MW68–70` | 1092–1094 | `ST_T_OUT` (0.1 °C), `ST_RH_OUT` (0.1 %), `ST_WIND` (0.1 m/s) | Weather |
| `%MW71–74` | 1095–1098 | `ST_T_IN` (0.1 °C), `ST_RH_IN` (0.1 %), `ST_CO2` (ppm), `ST_VPD` (0.01 kPa) | Greenhouse |
| `%MW75–76` | 1099–1100 | `ST_VENT_POS`, `ST_VENT_SP` | 0.1 % |
| `%MW77` | 1101 | `ST_CLIM_STATE` | §8.1 |
| `%MW78` | 1102 | `ST_CLIM_FLAGS` | b0 AUTO, b1 MANUAL, b2 rain, b3 wind limit, b4 storm, b5 net demand, b6 fog demand, b7 humidity venting, b8 TT-501 fallback, b9 COOL condition timing |
| `%MW79` | 1103 | `ST_FAN_STAGE` | 0–3 |
| `%MW80–81` | 1104–1105 | `ST_OUT1`, `ST_OUT2` | Output image: coils 0–15, 16–21 |
| `%MW82–83` | 1106–1107 | `ST_IN1`, `ST_IN2` | Input image: DI 0–15, 16–24 |
| `%MW84–87` | 1108–1111 | `ST_ALM1…4` | Latched alarms A00–A63 (§12) |
| `%MW88–91` | 1112–1115 | `ST_ACT1…4` | Alarm conditions present now |
| `%MW92–104` | 1116–1128 | `ST_ILK_*` | Interlock words, order of §11.2 |
| `%MW105–121` | 1129–1145 | `ST_DEV_*` | Device status words: XV-201, P-201, XV-301, XV-401…404, P-311…313, M-511, M-521, F-601…603, P-531, P-541 |
| `%MW122–133` | 1146–1157 | `ST_*_STARTS`, `ST_*_RUNMIN` | Starts and running minutes: P-201, F-601, F-602, F-603, P-531, P-541 |
| `%MW134–137` | 1158–1161 | `ST_XV401_CYC` … `ST_XV404_CYC` | Zone valve cycles |
| `%MW138–139` | 1162–1163 | `ST_M511_REV`, `ST_M521_CYC` | Vent reversals, net strokes |

### 9.3 Web HMI (`farmsim/hmi.py`, `farmsim/web/index.html`)
The HMI is a Modbus TCP client of the PLC. It polls every 250 ms: `%MW40–139` in one read, setpoints `%MW10–37`, and manual words `%MW1–6`. It serves a single page that refreshes every 500 ms. It uses only the registers above, so it runs unchanged against OpenPLC (`python -m farmsim hmi --plc <ip>:502 --plant none`).

| Page | Content (PRD HR-xx) |
|---|---|
| Overview | Mimic of the water system and greenhouse, weather strip, today's counters (HR-01) |
| Irrigation | Step chain, zone volume, radiation sum and interval, flags, zone table with diagnostics, daily totals, manual irrigation (HR-02) |
| Fertigation | EC and pH against the band, pH A/B, dosing outputs, stock tanks, dosing interlocks, 10 min trend, manual dosing (HR-03) |
| Climate | State chain, inside climate, weather, override flags, vent positioner, manual climate (HR-04) |
| Trends | Temperature/RH and vent/radiation over 2, 8 or 24 h; EC/pH over 10 min (HR-08) |
| Alarms | Active and cleared-not-reset alarms with class, RESET (HR-07) |
| Devices & I/O | Device state, interlock reasons, maintenance counters; DI/DO LEDs, scaled analog values (HR-07) |
| Settings | Every setpoint with limits, download per group, read-back "In PLC" (HR-06) |

**Control enables (HR-05).** A button is enabled only when the PLC would act on it (§5.1, §5.2). The PLC still checks every command.

| Control | Enabled when |
|---|---|
| START | Irrigation AUTO, and IDLE with the program disabled, or PAUSED; STOP circuit healthy |
| STOP | Irrigation AUTO, and steps 10–40, or IDLE with the program enabled |
| IRRIGATE NOW | Irrigation AUTO, IDLE, at least one zone enabled |
| ABORT | Irrigation AUTO, PAUSED |
| IRR MANUAL / AUTO | MANUAL in IDLE or FAULT; AUTO from MANUAL |
| CLIM MANUAL / AUTO | MANUAL at any time; AUTO from MANUAL |
| Manual devices | Their subsystem in MANUAL. The PLC clears the manual words while in AUTO, so no stale request survives a mode change |

**Time base.** The heartbeat `%MW40` counts 50 ms scans. The HMI turns its increase into process time, so trends are sampled every 1 s (EC, pH, flow; 10 min kept) and every 60 s (climate; 24 h kept) of process time. They therefore stay correct in fast-forward. The HMI does not need to know the speed. It shows the achieved speed (process s per wall s) next to the clock. A counter jump larger than 900 s (PLC restart) is not added.

**Comms watchdog (HR-09).** Comms are healthy while the heartbeat changes within 2 s of wall time. Otherwise the header shows the fault and the pages are dimmed, even if Modbus still answers (a stopped PLC).

**Field simulation registers (HR-11).** The demo panel talks to the plant server, not the PLC. It is a test-bench tool and not part of the operator HMI.

| Register | Content |
|---|---|
| HR 100–102 | Fault injection bits, `plant.FAULTS` order |
| HR 103 | Panel push-buttons: b0 START, b1 STOP, b2 RESET (self-clearing) |
| HR 104 | Weather scenario: 0 clear, 1 cloudy, 2 rain, 3 storm |
| HR 105 | Set the clock: minutes since midnight + 1 (self-clearing) |
| HR 106 | Fast-forward speed request, 1/5/20/40 × (self-clearing, fast mode only) |
| IR 32–46 | Plant truth: temperature, RH, vent, net, EC, pH, flow, pressure, level, CO₂, coupler watchdog, day, speed, fast-forward flag, field-check bits (what a technician would see on site; used by the troubleshooting trainer) |

## 10. Device blocks
`FB_Motor` and `FB_Valve` are reused from the template unchanged in interface: auto request, manual mode and request, interlock word, and (motors) feedback with 2 s discrepancy lockout. Status word: b0 requested, b1 commanded, b2 running (feedback), b3 blocked, b4 discrepancy, b5 manual.

`FB_Actuator` (new) drives a reversing motor with end limits and optional position feedback:

| Bit | Meaning |
|---|---|
| 0 / 1 | Open / close requested |
| 2 / 3 | Opening / closing (contactor commanded) |
| 4 / 5 | At open / closed limit |
| 6 | Blocked by interlock |
| 7 | Travel fault, locked out |
| 8 | Motor protection tripped |
| 9 | Manual mode |

Counters (starts, minutes, cycles) are not retained through a PLC restart in v1 (`RETAIN` on a production PLC).

## 11. Interlocks

An output is energised only when its **request** (sequence, state machine or manual) **and** its permissive are TRUE, every scan, in every mode.

### 11.1 Cause & effect
| Cause ↓ / Effect → | XV-201 | P-201 | XV-301 | XV-40x | P-311/312 | P-313 | Vent open | Vent close | Net deploy | Net retract | F-60x | P-531 | P-541 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| E-stop | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ |
| LT-201 ≥ 95 % or LT-201 fault | ✕ | | | | | | | | | | | | |
| LSL-201 dry | | ✕ | | | | | | | | | | | |
| No flow path (XV-301 and all XV-40x not commanded) | | ✕ | | | | | | | | | | | |
| A05 pressure high latched / PT-201 fault | | ✕ | | | | | | | | | | | |
| P-201 not running (feedback), FT-201 < 500 L/h or not yet for 3 s, or FT fault | | | | | ✕ | ✕ | | | | | | | |
| Stock A or B low | | | | | ✕ | | | | | | | | |
| Acid low | | | | | | ✕ | | | | | | | |
| EC fault / A07 EC high-high latched | | | | ✕ (A07) | ✕ | | | | | | | | |
| pH invalid / A08 pH low-low latched | | | | ✕ (A08) | | ✕ | | | | | | | |
| Motor protection (M511_OK / M521_OK) or travel lockout | | | | | | | ✕ | ✕ | ✕ (521) | ✕ (521) | | | |
| At own end limit | | | | | | | ✕ (ZSO) | ✕ (ZSC) | ✕ (ZSC) | ✕ (ZSO) | | | |
| Opposite contactor on / 0.5 s reversal pause | | | | | | | ✕ | ✕ | ✕ | ✕ | | | |
| Any fan commanded | | | | | | | ✕ | | | | | | |
| Vents not closed (ZSC-511 not made and ZT-511 > 5 %) | | | | | | | | | | | ✕ | | |
| Wind ≥ storm or ST-101 fault | | | | | | | | | ✕ | | | | |
| Pad sump low | | | | | | | | | | | | ✕ | |
| RH ≥ 90 % or MT-501 fault | | | | | | | | | | | | | ✕ |
| Own discrepancy lockout | | ✕ | | | ✕ | ✕ | | | | | ✕ (that fan) | ✕ | ✕ |
| Irrigation trip latched (AUTO → step 99) | ✕¹ | ✕ | ✕ | ✕ | ✕ | ✕ | | | | | | | |

✕ = output forced OFF. ¹ Only the sequence's requests are dropped; tank refill (§6.4) is not a sequence request and continues.

### 11.2 Interlock words (bit set = permissive missing; bit 0 is always E-stop)
| # | Word | b1 | b2 | b3 | b4 | b5 | b6 | b7 | b8 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `ilk_refill` (XV-201) | LT-201 fault | level ≥ 95 % | | | | | | |
| 1 | `ilk_pump` (P-201) | LSL-201 dry | no flow path | A05 latched | PT-201 fault | A04 lockout | | | |
| 2 | `ilk_return` (XV-301) | | | | | | | | |
| 3 | `ilk_zone` (XV-401…404) | A07 latched | A08 latched | | | | | | |
| 4 | `ilk_dose_ab` (P-311, P-312) | P-201 not running | flow < 500 L/h (3 s) | FT-201 fault | stock A low | stock B low | EC fault or A07 | P-311 lockout | P-312 lockout |
| 5 | `ilk_acid` (P-313) | P-201 not running | flow < 500 L/h (3 s) | FT-201 fault | acid low | pH invalid or A08 | P-313 lockout | | |
| 6 | `ilk_vent_open` | motor protection | A36 lockout | at open limit | fan commanded | reversal | | | |
| 7 | `ilk_vent_close` | motor protection | A36 lockout | at closed limit | reversal | | | | |
| 8 | `ilk_net_deploy` | motor protection | A37 lockout | at closed limit | storm / wind fault | reversal | | | |
| 9 | `ilk_net_retract` | motor protection | A37 lockout | at open limit | reversal | | | | |
| 10 | `ilk_fan` (F-601…603) | vents not closed | | | | | | | |
| 11 | `ilk_pad` (P-531) | pad sump low | A43 lockout | | | | | | |
| 12 | `ilk_fog` (P-541) | RH ≥ 90 % | MT-501 fault | A45 lockout | | | | | |

Stock A and B share one word on purpose: if either tank or either pump fails, both stop, so the 1 : 1 ratio is never broken. Fan lockouts are per fan and appear in that fan's device status, not in the shared word.

## 12. Alarms

Alarms latch. RESET sets `alm_latch := alm_act` (per word), so an alarm resets only once its condition has gone. Classes: **Trip** (in `TRIP_IRR`: irrigation → FAULT 99), **Lockout** (the device is blocked while latched), **Alarm** (high priority, no automatic action), **Warning**.

### 12.1 Alarm list
| Bit | Text | Condition | Delay | Class |
|---|---|---|---|---|
| A00 | E-stop pressed | `NOT ESTOP_OK` | — | Trip (all outputs off) |
| A01 | Clock fault | §5.3 | 150 s | Warning |
| A02 | LSL-201 T-201 low (dry-run) | `NOT LSL201_OK` | 2 s | Trip |
| A03 | T-201 refill failure | §6.4 | 600 s | Warning |
| A04 | P-201 feedback discrepancy | `P201 XOR P201_FB` | 2 s | Trip + lockout |
| A05 | PT-201 pressure high (blocked line) | ≥ 3.9 bar | 1 s | Trip |
| A06 | PT-201 pressure low (burst pipe / lost prime) | < 0.8 bar, P-201 running | 15 s | Trip |
| A07 | EC high-high | §7.3 | 5 s | Trip |
| A08 | pH low-low | §7.3 | 5 s | Trip |
| A09 | pH probe deviation | §7.4 | 10 s | Trip |
| A10 | Fertigation out of band | step 10 or 25 for 180 s (timer of the current step) | — | Trip |
| A11 | Stock tank A low | `NOT LSL311_OK` | 2 s | Warning |
| A12 | Stock tank B low | `NOT LSL312_OK` | 2 s | Warning |
| A13 | Acid tank low | `NOT LSL313_OK` | 2 s | Warning |
| A14 | P-311 feedback discrepancy | | 2 s | Trip + lockout |
| A15 | P-312 feedback discrepancy | | 2 s | Trip + lockout |
| A16 | P-313 feedback discrepancy | | 2 s | Trip + lockout |
| A17 | Zone flow high (leak / broken dripper) | §6.3 | 20 s | Warning |
| A18 | Zone flow low (clogged / valve) | §6.3 | 20 s | Warning |
| A19 | Zone shot timeout, zone skipped | §6.3 | — | Warning |
| A20 | LT-201 signal fault | < 3.6 mA | 1 s | Warning |
| A21 | FT-201 signal fault | < 3.6 mA | 1 s | Trip |
| A22 | PT-201 signal fault | < 3.6 mA | 1 s | Trip |
| A23 | AIT-301 EC signal fault | < 3.6 mA | 1 s | Trip |
| A24 | AIT-302 pH-A signal fault | < 3.6 mA | 1 s | Warning |
| A25 | AIT-303 pH-B signal fault | < 3.6 mA | 1 s | Warning |
| A26 | pH measurement lost (both probes) | A24 and A25 conditions | 1 s | Trip |
| A27 | FT-402 drain signal fault | < 3.6 mA | 1 s | Warning |
| A28 | Drain % out of range | §6.5 | — | Warning |
| A29 | RT-101 radiation signal fault | < 3.6 mA | 1 s | Warning |
| A30 | ST-101 wind signal fault (storm assumed) | < 3.6 mA | 1 s | Warning |
| A31 | TT-101 / MT-101 outside signal fault | < 3.6 mA | 1 s | Warning |
| A32 | TT-501 greenhouse temperature signal fault | < 3.6 mA | 1 s | Alarm |
| A33 | MT-501 greenhouse RH signal fault | < 3.6 mA | 1 s | Warning |
| A34 | AT-502 CO2 signal fault | < 3.6 mA | 1 s | Warning |
| A35 | ZT-511 vent position signal fault | < 3.6 mA | 1 s | Warning |
| A36 | Vent travel fault | §8.4 | — | Lockout |
| A37 | Shade net travel fault | §8.5 | — | Lockout |
| A38 | Vent motor protection tripped | `NOT M511_OK` | 1 s | Lockout |
| A39 | Shade net motor protection tripped | `NOT M521_OK` | 1 s | Lockout |
| A40 | F-601 feedback discrepancy | | 2 s | Lockout |
| A41 | F-602 feedback discrepancy | | 2 s | Lockout |
| A42 | F-603 feedback discrepancy | | 2 s | Lockout |
| A43 | P-531 pad pump feedback discrepancy | | 2 s | Lockout |
| A44 | Pad sump low | `NOT LSL531_OK` | 5 s | Warning |
| A45 | P-541 fog pump feedback discrepancy (incl. low inlet pressure stop) | | 2 s | Lockout |
| A46 | Greenhouse temperature high | T ≥ 38 °C | 60 s | Warning |
| A47 | Greenhouse temperature high-high (crop damage) | T ≥ 42 °C | 60 s | Alarm |
| A48 | CO2 low | < 300 ppm | 10 min | Warning |
| A49–A63 | spare | | | |

`TRIP_IRR` = A00, A02, A04–A10, A14–A16, A21–A23, A26.

### 12.2 Sensor fallbacks (summary)
| Sensor | Fallback |
|---|---|
| LT-201 | Refill blocked; LSL-201 still protects the pump; overflow pipe protects against overfill |
| FT-201, PT-201, AIT-301 | Irrigation trips (shots can't be metered, bursts not detected, EC not controlled) |
| AIT-302 / AIT-303 | Use the other probe (§7.4) |
| FT-402 | Drain % frozen, A28 suppressed |
| RT-101 | Radiation sum frozen (cycles on `SP_MAX_INT`), net on temperature only |
| ST-101 | Storm assumed: vents closed, net retracted, COOL allowed |
| TT-501 | Vent at 50 % (weather limits still apply), COOL and fog blocked, net on radiation only |
| MT-501 | Humidity venting and fog off |
| ZT-511 | Vent driven to limit switches only (≥ 50 % → open, else closed) |
| Clock | Daylight test replaces the day window (§5.3) |
| Rain detector wire break | Reads as rain: vents to rain position |

### 12.3 Stack light (irrigation panel)
| Lamp | Meaning |
|---|---|
| Green steady | Irrigation AUTO with program enabled, no trip |
| Amber steady | PAUSED, any MANUAL mode, program disabled, or a warning present |
| Red steady | Trip, lockout or alarm condition present |
| Red flashing 1 Hz | Condition gone, RESET required |

## 13. Communication failure, PLC stop and power loss
- **Remote I/O lost**: OpenPLC zeroes the PLANT inputs (*Set to zero* on every read group). `ESTOP_OK` = 0 trips with A00, all outputs off. *Verified on Runtime v4.3.2 (FAT OPL-08): trip 0.06 s after the plant went down.* The I/O coupler's own watchdog de-energises its outputs after 1 s without a write, so the field is safe even if the PLC can't write. The virtual plant implements this watchdog.
- **HMI lost**: the process continues. Commands are one-shot, so nothing stays latched. Panel buttons and E-stop still work.
- **PLC stopped or powered off**: outputs de-energise: zone, refill and return valves close (NC solenoids), all pumps and fans stop, the vent and the net stay where they are. Dosing stops with the pumps.
- **Power return**: cold start, both subsystems AUTO, irrigation program enabled, setpoints at defaults (§14-3, §14-7). The safety relay needs a manual reset, then RESET clears A00.

## 14. Open design items
| # | Item | Proposal |
|---|---|---|
| 1 | ~~The HMI map uses `%MW0–139`; the template's OpenPLC project backs only 64 words.~~ | **Closed in phase 4**: `make_openplc_project.py` sets the `%MW` count to 256; the image check reports no issues and `%MW139` reads on Runtime v4.3.2 (OPL-02). |
| 2 | Time of day comes from an I/O clock register. | On real hardware: NTP-synchronised clock in the I/O coupler or a gateway writing the register. |
| 3 | Restart after power return needs an operator to reset the safety relay, so an unattended farm is not watered after a night-time power cut. | Discuss with the grower: keep manual reset (personnel safety first), add a remote alarm (SMS gateway) in a later phase. |
| 4 | Zone valves have no position feedback. | Accepted: the flow deviation check (§6.3) detects a valve that does not open. |
| 5 | One vent group, no wind direction. | Accepted for v1; windward/leeward vents need a wind-direction sensor and a second actuator. |
| 6 | The 1 s tick counts scans, which ties the program to the 50 ms task. | Accepted: constants `SCANS_PER_S` and `DT_SCAN` are next to the task configuration with a comment. |
| 7 | Setpoints return to defaults after a PLC restart. | Declare the setpoint block `RETAIN` on a production PLC. OpenPLC v4 retain support not tried yet (phase 4 covered OPL-01…08 only). |
| 8 | Drain is measured in Z1 only. | Accepted (one measuring gutter per crop is common practice). |

## 15. Constants (`VAR CONSTANT`)
| Name | Value | Purpose |
|---|---|---|
| `SCANS_PER_S` / `DT_SCAN` | 20 / 0.05 s | Time base (§5.3) |
| `TRIP_IRR1` / `TRIP_IRR2` | 16#C7F5 / 16#04E1 | Irrigation trip mask (alarm words 1, 2) |
| `RED1..3` / `WARN1..3` | 16#C7F5, 16#04E1, 16#AFF1 / complements | Stack-light classes |
| `REFILL_ON` / `REFILL_OFF` / `LEVEL_HI_ILK` | 40 / 85 / 95 % | Tank refill |
| `PRESS_HI` / `PRESS_LO` | 3.9 / 0.8 bar | A05 / A06 (a clogged zone reaches 3.8 bar; shut-off 4.0) |
| `FLOW_DOSE_MIN` | 500 L/h, for 3 s | Dosing permissive |
| `T_BAND_OK` / `T_BAND_OUT` / `T_BAND_MAX` | 10 / 10 / 180 s | In-band confirm, out-of-band to HOLD, A10 |
| `T_OVERLAP` | 2 s | Zone changeover |
| `ZONE_FLOW_HI` / `ZONE_FLOW_LO` | 1.25 / 0.75 × reference | A17 / A18 |
| `EC_HH_MARGIN` / `PH_LL` / `PH_DEV` | 1.0 mS/cm / 4.5 / 0.3 | Crop protection, pH validation |
| `EC_BASE` / `FF_EC_DIV` / `FF_ACID` | 0.3 / 80 / 13.0 | Feedforward (§7.1) |
| `EC_KP` / `EC_TI` / `EC_IZONE` | 8 / 12 s / 0.5 mS/cm | EC PI (§7.1) |
| `PH_KP` / `PH_TI` / `PH_IZONE` | 5 / 12 s / 0.5 | pH PI (§7.1) |
| `VENT_KP` / `VENT_TI` / `VENT_DT` | 15 / 600 s / 5 s | Vent temperature PI |
| `VENT_DB` / `VENT_STOP` / `T_REVERSE` | 2.0 / 0.5 % / 0.5 s | Positioner |
| `VENT_FALLBACK` / `VENT_WIND_MAX` / `VENT_CLOSED` | 50 / 30 / 5 % | Fallbacks and limits |
| `HUM_GAIN` / `HUM_MAX` | 5 %/% / 50 % | Humidity demand |
| `NET_RAD_HYST` / `NET_T_ON` / `NET_T_OFF` | 150 W/m² / 4.0 / 2.0 °C | Shade net |
| `FOG_ON` / `FOG_OFF` / `FOG_VPD_HYST` / `RH_FOG_MAX` | 10 s / 50 s / 0.30 kPa / 90 % | Fogging |
| `COOL_EXIT` / `T_PREWET` / `T_PADDRY` | 3.0 °C / 60 s / 300 s | COOL state |
| `T_VENT_STALL` / `T_VENT_MAX` / `T_NET_MAX` | 15 / 180 / 150 s | Travel supervision |
| `TEMP_HI` / `TEMP_HH` / `CO2_LO` | 38 / 42 °C / 300 ppm | A46 / A47 / A48 |
| `DRAIN_LO` / `DRAIN_HI` / `DRAIN_MIN_CYC` | 10 / 50 % / 5 | A28 |
| `IRR_ENABLE_AT_START` | TRUE | §5.1 |
