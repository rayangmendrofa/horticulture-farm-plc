# Troubleshooting and maintenance guide — GH-1

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
| Zones get less water than counted, no alarm | [Return valve XV-301 passing](#return-valve-xv-301-passing), [FT-201 reads 20 % high (calibration)](#ft-201-reads-20--high-calibration) |
| One zone waters longer than the others, no alarm | [Zone 2 drippers partly clogged](#zone-2-drippers-partly-clogged) |
| Dosing runs higher than usual, no alarm | [Stock tank A mixed too weak](#stock-tank-a-mixed-too-weak), [Return valve XV-301 passing](#return-valve-xv-301-passing) |
| Crop grows slowly, EC on the HMI is perfect | [AIT-301 EC reads 0.4 mS/cm high (calibration drift)](#ait-301-ec-reads-04-mscm-high-calibration-drift) |
| House hot, pad-and-fan never starts | [TT-501 reads 3 °C low (calibration drift)](#tt-501-reads-3-c-low-calibration-drift), ST-101 fault (storm assumed, [ST-101 wind loop open](#st-101-wind-loop-open)) |
| Vents stay nearly closed on a dry day | [Rain sensor wire broken](#rain-sensor-wire-broken) |
| pH probes disagree (A09) | [pH probe B drifting](#ph-probe-b-drifting) |
| A motor locks out (A04, A14–A16, A38–A45) | the device's breaker (-Q…/-F…), §5 |
| Out of band, then HOLD and A10 | empty stock or acid tank, a dosing pump, the analysers |

## 4. Alarm reference
| Tag | Alarm | Class | First checks |
|---|---|---|---|
| A00 | E-stop pressed | trip | E-stop stations, safety relay -K0 LEDs, safety circuit wiring |
| A01 | Clock fault | warning | HMI clock vs real time; coupler clock/NTP |
| A02 | LSL-201 T-201 low (dry-run) | trip | T-201 sight tube; refill (XV-201, A03); LSL-201 switch |
| A03 | T-201 refill failure | warning | XV-201 coil voltage, valve, supply pressure, strainer |
| A04 | P-201 feedback discrepancy | trip | -Q201 tripped? -K201 picking up? feedback contact wiring |
| A05 | PT-201 pressure high (blocked line) | trip | Strainer, manual valves, zone valves opening |
| A06 | PT-201 pressure low (burst pipe / lost prime) | trip | Walk the main line: burst, open drain valve; pump primed? |
| A07 | EC high-high | trip | Hand-held EC at a dripper; stock strength; AIT-301 calibration |
| A08 | pH low-low | trip | Hand-held pH at a dripper; acid pump stuck on; analyser calibration |
| A09 | pH probe deviation | trip | Hand-held pH of a sample: which probe is wrong? |
| A10 | Fertigation out of band | trip | Stock and acid levels, dosing pumps, analysers; why EC/pH cannot reach band |
| A11 | Stock tank A low | warning | Stock tank A level, LSL-311 |
| A12 | Stock tank B low | warning | Stock tank B level, LSL-312 |
| A13 | Acid tank low | warning | Acid tank level, LSL-313 (PPE) |
| A14 | P-311 feedback discrepancy | trip | -F311, pump fault LED, suction |
| A15 | P-312 feedback discrepancy | trip | -F312, pump fault LED, suction |
| A16 | P-313 feedback discrepancy | trip | -F313, pump fault LED |
| A17 | Zone flow high (leak / broken dripper) | warning | Walk the zone: leak, lateral off, broken dripper |
| A18 | Zone flow low (clogged / valve) | warning | Bucket test; precipitate or biofilm; zone valve fully open? |
| A19 | Zone shot timeout, zone skipped | warning | Zone flow very low or zero: valve, clogging, pressure |
| A20 | LT-201 signal fault | warning | Loop current LT-201 (0 mA = open loop) |
| A21 | FT-201 signal fault | trip | Loop current FT-201; flowmeter display |
| A22 | PT-201 signal fault | trip | Loop current PT-201; local gauge |
| A23 | AIT-301 EC signal fault | trip | Loop current AIT-301; analyser power |
| A24 | AIT-302 pH-A signal fault | warning | Loop current AIT-302; probe cable |
| A25 | AIT-303 pH-B signal fault | warning | Loop current AIT-303; probe cable |
| A26 | pH measurement lost (both probes) | trip | Both pH analysers: power, cables, probes |
| A27 | FT-402 drain signal fault | warning | Loop current FT-402; drain gutter sensor |
| A28 | Drain % out of range | warning | Shot size vs crop demand; FT-402 and FT-201 readings |
| A29 | RT-101 radiation signal fault | warning | Loop current RT-101; pyranometer dome |
| A30 | ST-101 wind signal fault (storm assumed) | warning | Loop current ST-101; anemometer turning |
| A31 | TT-101 / MT-101 outside signal fault | warning | Loop currents TT-101 / MT-101; weather-station cable |
| A32 | TT-501 greenhouse temperature signal fault | alarm | Loop current TT-501; aspirated sensor box |
| A33 | MT-501 greenhouse RH signal fault | warning | Loop current MT-501 |
| A34 | AT-502 CO2 signal fault | warning | Loop current AT-502; analyser |
| A35 | ZT-511 vent position signal fault | warning | Loop current ZT-511; position transmitter |
| A36 | Vent travel fault | lock-out | Vent drive: jammed, coupling, gear; motor turning? |
| A37 | Shade net travel fault | lock-out | Net drive: snagged fabric, pull wire |
| A38 | Vent motor protection tripped | lock-out | -Q511 tripped; drive free? |
| A39 | Shade net motor protection tripped | lock-out | -Q521 tripped; net free? |
| A40 | F-601 feedback discrepancy | lock-out | -Q601, belt, bearings |
| A41 | F-602 feedback discrepancy | lock-out | -Q602, belt, bearings |
| A42 | F-603 feedback discrepancy | lock-out | -Q603, belt, bearings |
| A43 | P-531 pad pump feedback discrepancy | lock-out | -Q531; sump level; impeller |
| A44 | Pad sump low | warning | Float valve, clean-water supply, sump leak |
| A45 | P-541 fog pump feedback discrepancy | lock-out | -Q541; inlet pressure and fine filter |
| A46 | Greenhouse temperature high | warning | Vents, net, fans working? Set points sensible? |
| A47 | Greenhouse temperature high-high (crop damage) | alarm | Cooling capacity, failed fans or pads; crop damage risk |
| A48 | CO2 low | warning | Vents wide open with a dense crop; AT-502 calibration |

## 5. Fault reference
Ordered by how hard they are to find.

### E-stop pressed
*Difficulty 1: an alarm points to it. Simulator fault id: `estop`.*

| | |
|---|---|
| **Symptoms** | A00, every output off, irrigation in FAULT (99), red lamp. RESET is refused while the button is in. |
| **Confirm** | Walk the E-stop stations (irrigation panel, pump station); check the safety relay -K0 LEDs. |
| **Root cause** | Someone pressed an E-stop, or the safety circuit opened (loose wire, failed relay). |
| **Fix** | Find out why it was pressed. Release, reset -K0, RESET on the HMI, then START. |

### T-201 low level (LSL-201 dry)
*Difficulty 1: an alarm points to it. Simulator fault id: `lsl201_dry`.*

| | |
|---|---|
| **Symptoms** | A02 trip; P-201 blocked (dry-run protection). |
| **Confirm** | Compare LT-201 with the tank's sight tube. If the tank is really low, check refill (XV-201, A03). |
| **Root cause** | Tank empty (refill failed or water used faster than refilled), or a failed/dirty LSL switch. |
| **Fix** | Restore the level, find why refill did not keep up, RESET. |

### Refill valve XV-201 fails to open
*Difficulty 1: an alarm points to it. Simulator fault id: `refill_fail`.*

| | |
|---|---|
| **Symptoms** | A03 warning: XV-201 commanded for 10 min with less than 2 % level rise. The tank keeps falling; later A02 and a trip. |
| **Confirm** | DO LED and 24 V at the XV-201 solenoid; manual override on the valve; supply pressure and the inlet strainer. |
| **Root cause** | Burnt solenoid coil, stuck valve, no supply pressure (well pump off, mains shut). |
| **Fix** | Repair, then test a refill in IRR MANUAL. Check the well pump. |

### LT-201 tank level loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `lt201_break`.*

| | |
|---|---|
| **Symptoms** | A20 warning; level frozen at the last good value; refill blocked. Irrigation continues, protected by LSL-201. |
| **Confirm** | Loop current at the -A1 analog terminal in series (0 mA = open loop); junction box, transmitter. |
| **Root cause** | Broken cable, loose terminal, water in the junction box, failed transmitter. |
| **Fix** | Repair, then check 4/12/20 mA with a loop calibrator (I/O checkout). |

### FT-201 flow loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `ft201_break`.*

| | |
|---|---|
| **Symptoms** | A21 trip: shot metering and dosing are impossible without flow. |
| **Confirm** | Loop current at -A1; flowmeter display/LED; cable to the pump station. |
| **Root cause** | Broken cable or failed flowmeter electronics. |
| **Fix** | Repair; verify the reading against a timed volume (bucket and stopwatch on one zone). |

### PT-201 pressure loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `pt201_break`.*

| | |
|---|---|
| **Symptoms** | A22 trip; pump blocked (pressure protection lost). |
| **Confirm** | Loop current at -A1; compare with the local gauge. |
| **Root cause** | Broken cable or failed transmitter. |
| **Fix** | Repair; check zero with the line drained and one point against the gauge. |

### AIT-301 EC loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `ec_break`.*

| | |
|---|---|
| **Symptoms** | A23 trip; A/B dosing blocked (interlock names 'EC signal fault'). |
| **Confirm** | Loop current from the EC analyser; analyser display and power. |
| **Root cause** | Broken cable, analyser fault, analyser powered off. |
| **Fix** | Repair; then check the EC against a hand-held meter in the line. |

### AIT-302 pH probe A loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `ph_a_break`.*

| | |
|---|---|
| **Symptoms** | A24 warning; the PLC controls on probe B alone (1oo2 with fallback). Irrigation continues. |
| **Confirm** | Loop current; analyser A display; probe cable. |
| **Root cause** | Broken probe cable or analyser fault. |
| **Fix** | Repair soon: with one probe left, the next failure trips irrigation (A26). |

### AIT-303 pH probe B loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `ph_b_break`.*

| | |
|---|---|
| **Symptoms** | A25 warning; the PLC controls on probe A alone. |
| **Confirm** | Loop current; analyser B display; probe cable. |
| **Root cause** | Broken probe cable or analyser fault. |
| **Fix** | Repair soon: one more failure trips irrigation (A26). |

### FT-402 drain flow loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `ft402_break`.*

| | |
|---|---|
| **Symptoms** | A27 warning; drain % stops updating. Irrigation continues. |
| **Confirm** | Loop current; the drain gutter's flow sensor (often blocked by substrate fines). |
| **Root cause** | Broken cable, failed sensor. |
| **Fix** | Repair; check the drain % against a manual collection over one cycle. |

### RT-101 radiation loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `rt101_break`.*

| | |
|---|---|
| **Symptoms** | A29 warning; radiation sum frozen, so cycles start on the maximum interval only; the shade net follows temperature only. |
| **Confirm** | Loop current from the weather station; pyranometer dome clean and cable intact. |
| **Root cause** | Broken cable, failed pyranometer or its transmitter. |
| **Fix** | Repair; compare with a neighbouring station or the clear-sky value at noon. |

### ST-101 wind loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `st101_break`.*

| | |
|---|---|
| **Symptoms** | A30 warning; storm assumed: vents closed, shade net retracted, even in calm weather. The house heats up. |
| **Confirm** | Loop current; anemometer cups turning freely; mast cable. |
| **Root cause** | Broken cable or failed anemometer. Fail-safe design: no wind signal is treated as a storm. |
| **Fix** | Repair quickly (the house overheats with closed vents); spin-test the anemometer. |

### TT-101 / MT-101 outside sensor loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `tt101_break`.*

| | |
|---|---|
| **Symptoms** | A31 warning; outside temperature and humidity frozen; climate decisions that use them fall back. |
| **Confirm** | Loop currents of both channels; the radiation screen of the sensor. |
| **Root cause** | Shared cable to the weather station cut, or the combined sensor failed. |
| **Fix** | Repair; compare with a hand-held thermo-hygrometer in the shade. |

### TT-501 greenhouse temperature loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `tt501_break`.*

| | |
|---|---|
| **Symptoms** | A32 alarm; climate in temperature fallback (flag shown on the Climate page); fogging blocked. |
| **Confirm** | Loop current; the aspirated sensor box (fan running?); cable along the truss. |
| **Root cause** | Broken cable, failed sensor or its aspiration fan. |
| **Fix** | Repair with priority: climate control is degraded. |

### MT-501 greenhouse humidity loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `mt501_break`.*

| | |
|---|---|
| **Symptoms** | A33 warning; humidity venting and fogging blocked (fog interlock names the MT-501 fault). |
| **Confirm** | Loop current; sensor in the aspirated box. |
| **Root cause** | Broken cable or failed humidity sensor (they age in a humid house). |
| **Fix** | Repair or replace; check against a hand-held hygrometer. |

### AT-502 CO2 loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `at502_break`.*

| | |
|---|---|
| **Symptoms** | A34 warning; CO2 display frozen. Control is not affected (CO2 is monitored only). |
| **Confirm** | Loop current; analyser power and its sample filter. |
| **Root cause** | Broken cable or failed analyser. |
| **Fix** | Repair when convenient. |

### ZT-511 vent position loop open
*Difficulty 1: an alarm points to it. Simulator fault id: `zt511_break`.*

| | |
|---|---|
| **Symptoms** | A35 warning; the vent positioner loses its feedback and can only drive to the limit switches. |
| **Confirm** | Loop current; the potentiometer/encoder on the rack-and-pinion drive. |
| **Root cause** | Broken cable or failed position transmitter. |
| **Fix** | Repair; recalibrate 0 and 100 % at the limit switches. |

### Burst pipe on the main line
*Difficulty 1: an alarm points to it. Simulator fault id: `burst_pipe`.*

| | |
|---|---|
| **Symptoms** | A06 trip: pressure low with the pump running; flow higher than any zone explains. |
| **Confirm** | Walk the main line: wet ground, spray. FT-201 against the zone reference flow. |
| **Root cause** | Mechanical damage, pressure surge, ageing PE pipe or fitting. |
| **Fix** | Isolate, repair, flush, then run one cycle and watch pressure and flow. |

### Blocked main line (strainer or valve)
*Difficulty 1: an alarm points to it. Simulator fault id: `blocked_line`.*

| | |
|---|---|
| **Symptoms** | A05 trip: pressure high with little or no flow. |
| **Confirm** | Strainer differential/inspection; manual valves in the header; zone valves really opening. |
| **Root cause** | Clogged strainer (algae, sand, precipitated fertiliser), closed manual valve. |
| **Fix** | Clean the strainer, open the valve, RESET. Review the filter maintenance interval. |

### Stock tank A empty
*Difficulty 1: an alarm points to it. Simulator fault id: `stock_a_empty`.*

| | |
|---|---|
| **Symptoms** | A11 warning; A and B dosing both stop (they must stay in ratio), EC falls out of band, HOLD, then A10 trip after 180 s. |
| **Confirm** | Tank A level; LSL-311 switch. |
| **Root cause** | Concentrate used up. |
| **Fix** | Mix a new batch (same recipe as B), RESET. |

### Stock tank B empty
*Difficulty 1: an alarm points to it. Simulator fault id: `stock_b_empty`.*

| | |
|---|---|
| **Symptoms** | A12 warning; A and B dosing stop together; EC out of band, then A10. |
| **Confirm** | Tank B level; LSL-312 switch. |
| **Root cause** | Concentrate used up. |
| **Fix** | Mix a new batch, RESET. |

### Acid tank empty
*Difficulty 1: an alarm points to it. Simulator fault id: `acid_empty`.*

| | |
|---|---|
| **Symptoms** | A13 warning; acid dosing stops; pH rises out of band, HOLD, then A10. |
| **Confirm** | Acid tank level; LSL-313 switch. Wear acid PPE. |
| **Root cause** | Acid used up. |
| **Fix** | Refill (acid into water, never the reverse), RESET. |

### P-311 dosing pump A tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p311_trip`.*

| | |
|---|---|
| **Symptoms** | A14 trip: P-311 commanded but no running feedback; locked out until RESET. |
| **Confirm** | MCB -F311 and the pump's own fault LED; diaphragm and suction (air lock); 230 V at the pump. |
| **Root cause** | Overcurrent, pump fault, MCB tripped. |
| **Fix** | Repair, reset -F311, RESET A14; prime the pump. |

### P-312 dosing pump B tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p312_trip`.*

| | |
|---|---|
| **Symptoms** | A15 trip: P-312 commanded but no running feedback. |
| **Confirm** | MCB -F312, pump fault LED, suction. |
| **Root cause** | Overcurrent, pump fault, MCB tripped. |
| **Fix** | Repair, reset -F312, RESET A15; prime the pump. |

### P-313 acid pump tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p313_trip`.*

| | |
|---|---|
| **Symptoms** | A16 trip: P-313 commanded but no running feedback. |
| **Confirm** | MCB -F313, pump fault LED; acid-resistant parts (PPE). |
| **Root cause** | Overcurrent, pump fault, corroded connector. |
| **Fix** | Repair, reset -F313, RESET A16. |

### P-201 irrigation pump overload tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p201_trip`.*

| | |
|---|---|
| **Symptoms** | A04 trip: P-201 commanded but no running feedback; locked out until RESET. |
| **Confirm** | Motor-protection breaker -Q201 tripped? Current per phase, insulation resistance, pump turning freely. |
| **Root cause** | Mechanical overload, blocked impeller, single phasing, winding fault. |
| **Fix** | Fix the cause before resetting -Q201; never just reset repeatedly. |

### Vent motor M-511 protection tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `m511_overload`.*

| | |
|---|---|
| **Symptoms** | A38 lock-out: motor protection -Q511 tripped; the vent cannot move. |
| **Confirm** | -Q511 trip indicator; current per phase; drive mechanically free? |
| **Root cause** | Overload from a stiff drive, both contactors pulled in (should be impossible: interlocked), motor fault. |
| **Fix** | Find the cause, reset -Q511, RESET. |

### Shade net motor M-521 protection tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `m521_overload`.*

| | |
|---|---|
| **Symptoms** | A39 lock-out: the net cannot move. |
| **Confirm** | -Q521 trip indicator; motor current; net free to move? |
| **Root cause** | Overload from a snagged net, motor fault. |
| **Fix** | Find the cause, reset -Q521, RESET. |

### Exhaust fan F-601 tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `f601_trip`.*

| | |
|---|---|
| **Symptoms** | A40 lock-out: F-601 commanded without running feedback; the next fan takes its place in the stage. |
| **Confirm** | -Q601 trip indicator; belt and bearings; current per phase. |
| **Root cause** | Overload, broken belt jammed in the pulley, bearing seizure. |
| **Fix** | Repair, reset -Q601, RESET. |

### Exhaust fan F-602 tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `f602_trip`.*

| | |
|---|---|
| **Symptoms** | A41 lock-out: F-602 commanded without running feedback; replaced by the next fan. |
| **Confirm** | -Q602 trip indicator; belt and bearings. |
| **Root cause** | Overload or mechanical fault. |
| **Fix** | Repair, reset -Q602, RESET. |

### Exhaust fan F-603 tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `f603_trip`.*

| | |
|---|---|
| **Symptoms** | A42 lock-out: F-603 commanded without running feedback. |
| **Confirm** | -Q603 trip indicator; belt and bearings. |
| **Root cause** | Overload or mechanical fault. |
| **Fix** | Repair, reset -Q603, RESET. |

### Pad pump P-531 tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p531_trip`.*

| | |
|---|---|
| **Symptoms** | A43 lock-out: the pads stay dry, so pad-and-fan cooling only ventilates. |
| **Confirm** | -Q531 trip indicator; pump running dry? sump level; impeller. |
| **Root cause** | Overload, dry running, blocked impeller. |
| **Fix** | Repair, reset -Q531, RESET. |

### Pad sump low
*Difficulty 1: an alarm points to it. Simulator fault id: `pad_sump_low`.*

| | |
|---|---|
| **Symptoms** | A44 warning; P-531 blocked (dry-run protection); pads dry out. |
| **Confirm** | Float valve feeding the sump; clean-water supply; leaks. |
| **Root cause** | Stuck float valve, closed supply, leak from the sump. |
| **Fix** | Restore the supply; the pump restarts on its own when the level returns. |

### Fog pump P-541 tripped
*Difficulty 1: an alarm points to it. Simulator fault id: `p541_trip`.*

| | |
|---|---|
| **Symptoms** | A45 lock-out: P-541 commanded without running feedback; no fogging. |
| **Confirm** | -Q541 trip indicator; high-pressure pump oil and seals; motor current. |
| **Root cause** | Overload or pump fault. |
| **Fix** | Repair, reset -Q541, RESET. |

### pH probe B drifting
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `ph_b_drift`.*

| | |
|---|---|
| **Symptoms** | A09 trip: the two pH probes disagree by more than the limit. The alarm does not say which probe is wrong. |
| **Confirm** | Take a sample at the analysers and measure it with a calibrated hand-held pH meter; the probe that disagrees is the bad one. Check its age and last calibration. |
| **Root cause** | Ageing glass electrode, fouled junction, calibration drift. |
| **Fix** | Clean and two-point calibrate (pH 4 and 7) or replace the probe; RESET. |

### I/O clock frozen
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `clock_frozen`.*

| | |
|---|---|
| **Symptoms** | A01 warning after 150 s; the clock on the HMI stops; the day window is replaced by 'daylight' (RT-101 above 50 W/m2 for 5 min). |
| **Confirm** | Compare the HMI clock with real time; the I/O coupler's clock/NTP status; a coupler restart that lost the time. |
| **Root cause** | Clock module failed, NTP server unreachable, coupler lost its time after a power cut. |
| **Fix** | Restore the time source; RESET. Irrigation kept working on daylight in the meantime. |

### Zone 3 drippers clogged
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `z3_clogged`.*

| | |
|---|---|
| **Symptoms** | A18 warning on zone 3: flow more than 25 % below the reference; the shot takes much longer but the volume is still delivered (metered). |
| **Confirm** | Bucket test of several drippers in zone 3; inspect for precipitate (Ca phosphate) or root intrusion. |
| **Root cause** | Chemical precipitation (high pH, mixing A and B concentrates), biofilm, particles past the filter. |
| **Fix** | Acid flush the zone (pH ~2 for a short time) or replace laterals; check the filter. |

### Zone 4 leak / broken dripper
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `z4_leak`.*

| | |
|---|---|
| **Symptoms** | A17 warning on zone 4: flow more than 25 % above the reference. Shot completes quickly; plants near the leak are waterlogged, the rest under-watered. |
| **Confirm** | Walk zone 4 during a shot: wet patches, a lateral off its connector, a split pipe. |
| **Root cause** | Lateral pulled off, rodent damage, dripper missing. |
| **Fix** | Repair; re-run a shot and check the flow against the reference. |

### Roof vent jammed
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `vent_stuck`.*

| | |
|---|---|
| **Symptoms** | A36 lock-out: the vent motor runs but the position and limit switches do not change (travel fault). |
| **Confirm** | Look at the vent: rack-and-pinion jammed, broken drive shaft, obstruction, ice/debris. Is the motor turning? (If not, see the motor overload fault.) |
| **Root cause** | Mechanical jam, sheared coupling, broken gear. |
| **Fix** | Repair the drive; stroke the vent in CLIM MANUAL; RESET. |

### Shade net jammed
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `net_stuck`.*

| | |
|---|---|
| **Symptoms** | A37 lock-out: the net motor runs but no limit switch is reached in 150 s. |
| **Confirm** | Look at the net: snagged fabric, broken wire rope, drive shaft. |
| **Root cause** | Mechanical jam or broken pull wire. |
| **Fix** | Repair; run the net in CLIM MANUAL; RESET. |

### Fog pump inlet starved
*Difficulty 2: an alarm, but the cause needs reasoning. Simulator fault id: `fog_inlet_low`.*

| | |
|---|---|
| **Symptoms** | A45 lock-out like a pump trip, but -Q541 is not tripped: the pump's low-inlet-pressure switch stops it. |
| **Confirm** | Inlet pressure gauge; clean-water supply; the fine filter before the pump. |
| **Root cause** | Clogged fine filter, closed supply valve, low mains pressure. |
| **Fix** | Clean the filter or restore the supply; RESET. Never run the HP pump without inlet pressure. |

### Rain sensor wire broken
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `rain_wire_break`.*

| | |
|---|---|
| **Symptoms** | No alarm. The HMI shows 'rain' on a dry, sunny day and the vents never open beyond the rain limit (10 %); the house runs hot. |
| **Confirm** | Look outside, then at the input LED of RAIN_DRY (off = rain). Measure 24 V at the rain sensor terminals; check the sensor plate is dry. |
| **Root cause** | Broken wire or loose terminal in the NC rain circuit: fail-safe design reads it as rain. |
| **Fix** | Repair the wiring; test with a wet cloth on the sensor. |

### Return valve XV-301 passing
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `xv301_passing`.*

| | |
|---|---|
| **Symptoms** | No alarm. Every zone's flow reads about 20 % above its reference (just under the 25 % alarm), shots finish early, A/B dosing runs higher than usual and the drain % falls: the zones are getting less water than the PLC counts. |
| **Confirm** | During a shot, listen at XV-301 and feel the return line; a clamp-on flowmeter on the return pipe shows flow with the valve closed. FT-201 itself reads true. |
| **Root cause** | Worn seat or debris holding the return valve slightly open. |
| **Fix** | Overhaul or replace XV-301; compare the zone flows with their references afterwards. |

### Zone 2 drippers partly clogged
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `z2_partly_clogged`.*

| | |
|---|---|
| **Symptoms** | No alarm. Zone 2 flow is about 18 % below its reference (the alarm needs 25 %), so its shot takes longer than the others. Plants in some rows of zone 2 wilt at midday. |
| **Confirm** | Compare zone flows on the Irrigation page or the 10 min trend; bucket-test drippers along zone 2; look for white deposits. |
| **Root cause** | Early precipitation or biofilm, not yet bad enough to alarm. |
| **Fix** | Acid flush the zone; review the pH set point and filter maintenance. Consider a tighter flow-low limit. |

### FT-201 reads 20 % high (calibration)
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `ft201_reads_high`.*

| | |
|---|---|
| **Symptoms** | No alarm. Every zone reads about 20 % above its reference flow, shots end early, and the drain % drops: the crop gets less water than the PLC counts. |
| **Confirm** | Bucket test: time a known volume on one zone, or fit a clamp-on flowmeter next to FT-201. Here the return line is quiet (unlike a passing XV-301). |
| **Root cause** | Flowmeter calibration drift, wrong K-factor after a replacement, air in the line. |
| **Fix** | Recalibrate or correct the scaling; record as-found/as-left. |

### Stock tank A mixed too weak
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `stock_a_weak`.*

| | |
|---|---|
| **Symptoms** | No alarm. EC and pH are in band, but A/B dosing runs about a third higher than usual: the PLC makes up EC with extra B. The crop gets too much of B's nutrients and too little calcium/nitrate. |
| **Confirm** | Compare today's dosing outputs with the usual; measure the EC of a diluted sample of each stock tank (A and B should match). |
| **Root cause** | Mixing error: too little fertiliser or too much water in tank A. |
| **Fix** | Re-mix tank A to recipe; check with a diluted EC test before connecting it. |

### AIT-301 EC reads 0.4 mS/cm high (calibration drift)
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `ec_reads_high`.*

| | |
|---|---|
| **Symptoms** | No alarm. The HMI shows EC exactly on set point and dosing a bit lower than usual, but the crop actually gets EC 2.1 instead of 2.5; growth slows over days. |
| **Confirm** | Measure a sample from a dripper with a calibrated hand-held EC meter and compare with AIT-301. |
| **Root cause** | Fouled or drifted conductivity cell, wrong temperature compensation. |
| **Fix** | Clean and calibrate with a reference solution; check the dripper EC weekly. |

### TT-501 reads 3 °C low (calibration drift)
*Difficulty 3: no alarm: trends and a field check find it. Simulator fault id: `tt501_reads_low`.*

| | |
|---|---|
| **Symptoms** | No alarm. On a hot day the HMI shows about 30 °C while it is clearly hotter in the house; pad-and-fan cooling never starts and the vents open less than expected. |
| **Confirm** | Compare TT-501 with a calibrated reference thermometer in the same aspirated box; check the box fan and that the sensor is not in the sun. |
| **Root cause** | Sensor drift, failed aspiration fan (sensor heats unevenly), wrong scaling after replacement. |
| **Fix** | Recalibrate or replace; review the crop for heat stress since the last good calibration. |

## 6. Preventive maintenance
The PLC counts starts and running minutes of P-201, the fans and the pad and fog pumps, zone-valve cycles, vent reversals and net strokes (*Devices & I/O* page, `%MW122–139`). Use them to plan maintenance by use, not by calendar alone.

| Item | Interval (suggested) | Task | Catches |
|---|---|---|---|
| AIT-301 EC | weekly | Hand-held EC at a dripper vs AIT-301; clean the cell, calibrate monthly | Drift ([AIT-301 EC reads 0.4 mS/cm high (calibration drift)](#ait-301-ec-reads-04-mscm-high-calibration-drift)) |
| AIT-302/303 pH | 2 weeks | Two-point calibration (pH 4 and 7), one probe at a time so the other keeps control | Drift, ageing glass ([pH probe B drifting](#ph-probe-b-drifting)) |
| FT-201 | 6 months | Timed volume on one zone (bucket test) | Flow calibration ([FT-201 reads 20 % high (calibration)](#ft-201-reads-20--high-calibration)) |
| TT-501, MT-501 | 3 months | Compare with a reference thermo-hygrometer in the aspirated box; check the box fan | Drift ([TT-501 reads 3 °C low (calibration drift)](#tt-501-reads-3-c-low-calibration-drift)) |
| Zones Z1–Z4 | monthly | Zone flow vs reference on the Irrigation page; bucket-test 5 drippers per zone; acid flush when flow drops 10 % | Clogging ([Zone 2 drippers partly clogged](#zone-2-drippers-partly-clogged)) |
| Stock tanks A, B | every new batch | Diluted EC of each concentrate; A and B must match | Mixing errors ([Stock tank A mixed too weak](#stock-tank-a-mixed-too-weak)) |
| XV-301, zone valves | every 20 000 cycles or yearly | Seat leak test: return line quiet with the valve closed | Passing valves ([Return valve XV-301 passing](#return-valve-xv-301-passing)) |
| Strainer before the header | weekly in summer | Clean; note the pressure before/after | Blocked line (A05) |
| P-201, fans F-601…603 | yearly or per run hours | Insulation resistance (≥ 1 MΩ at 500 V DC), current per phase, bearings, fan belts | Trips, worn belts |
| Vent and net drives | 6 months | Stroke test, gearbox oil, limit-switch setting, reversal count vs last time | Travel faults (A36/A37) |
| Pads, pad sump | monthly in summer | Scale and algae, even wetting, float valve | Poor cooling, A44 |
| Fog pump P-541 | 500 h | Oil, seals, fine filter, nozzles | A45, dripping nozzles |
| E-stop circuit | 6 months | Functional test of every E-stop and the safety relay reset | Safety function failure |
