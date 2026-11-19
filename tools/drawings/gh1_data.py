"""GH-1 electrical data: devices, cables, feeders and the I/O channel wiring.

Single source for the drawing sheets, the terminal plan, the parts list and
docs/IO_CHECKOUT.md (tools/drawings/make_drawings.py). Channel order and PLC
addresses follow farmsim/tags.py and the FDS section 4 I/O list; a consistency
check in make_drawings.py compares them.
"""
from __future__ import annotations

PROJECT = "GH-1 Tropical Greenhouse"
DOC_PREFIX = "GH1-"
REV = "A"
DATE = "2026-11-19"
SUBTITLE = ("Irrigation, fertigation and climate control, 1 000 m² greenhouse",
            "OpenPLC Runtime v4 + Modbus TCP remote I/O",
            "Supply 3/N/PE AC 400/230 V 50 Hz")
SET_TITLE = "Electrical drawing set - control panel GH-1 (pump room)"

SHEETS = [
    ("E-00", "Cover sheet, index and legend"),
    ("E-01", "Power distribution and 24 V DC"),
    ("E-02", "Pump feeders P-201, P-531, P-541"),
    ("E-03", "Exhaust fan feeders F-601 ... F-603"),
    ("E-04", "Vent and shade net drives (reversing)"),
    ("E-05", "Dosing pumps P-311 ... P-313"),
    ("E-06", "Safety circuit"),
    ("E-07", "Digital inputs -A1.1 / -A1.2"),
    ("E-08", "Digital outputs -A1.3 / -A1.4"),
    ("E-09", "Analog inputs -A1.5 / -A1.6"),
    ("E-10", "Terminal plan -X2"),
    ("E-11", "Terminal plans -X1, -X3, -X4 and cables"),
    ("E-12", "Panel layout"),
    ("E-13", "Parts list"),
    ("E-14", "Network architecture"),
]
SCALED = {"E-12": "1:6"}

# --------------------------------------------------------------------------- feeders
# 3-phase direct-on-line motors: (motor, MPCB, contactor, tag, description, kW, In A, MPCB range,
#                                 cable, X4 terminals, DO channel, DI channel of the feedback)
DOL = [
    ("-M201", "-Q201", "-K201", "P-201", "Irrigation pump", 0.75, 1.9, "1.6-2.5 A", "-W11", 1, 1, 5),
    ("-M531", "-Q531", "-K531", "P-531", "Pad pump", 0.37, 1.0, "1.0-1.6 A", "-W12", 5, 17, 22),
    ("-M541", "-Q541", "-K541", "P-541", "Fog pump 70 bar", 2.2, 4.8, "4.0-6.3 A", "-W13", 9, 18, 24),
    ("-M601", "-Q601", "-K601", "F-601", "Exhaust fan 1", 1.1, 2.6, "2.5-4.0 A", "-W14", 13, 14, 19),
    ("-M602", "-Q602", "-K602", "F-602", "Exhaust fan 2", 1.1, 2.6, "2.5-4.0 A", "-W15", 17, 15, 20),
    ("-M603", "-Q603", "-K603", "F-603", "Exhaust fan 3", 1.1, 2.6, "2.5-4.0 A", "-W16", 21, 16, 21),
]
# reversing drives: (motor, MPCB, open K, close K, tag, description, kW, In, range, cable, X4 terms,
#                    open DO, close DO, healthy DI, open-limit dev, closed-limit dev, open meaning)
REV_DRIVES = [
    ("-M511", "-Q511", "-K511.1", "-K511.2", "M-511", "Roof vent drive", 0.37, 1.1, "1.0-1.6 A", "-W17", 25,
     10, 11, 15, "-B512", "-B513", "open"),
    ("-M521", "-Q521", "-K521.1", "-K521.2", "M-521", "Shade net drive", 0.37, 1.1, "1.0-1.6 A", "-W18", 29,
     12, 13, 18, "-B522", "-B523", "retract"),
]
# 230 V dosing pumps: (motor, MCB, contactor, tag, description, power cable, X4 L/N/PE, control cable,
#                      DO channel, DI feedback channel, AO channel)
DOSING = [
    ("-M311", "-F311", "-K311", "P-311", "Dosing pump A", "-W21", 33, "-W31", 7, 9, 0),
    ("-M312", "-F312", "-K312", "P-312", "Dosing pump B", "-W22", 36, "-W32", 8, 10, 1),
    ("-M313", "-F313", "-K313", "P-313", "Acid pump", "-W23", 39, "-W33", 9, 11, 2),
]

# --------------------------------------------------------------------------- I/O channels
# Digital inputs. kind: int1 (one internal contact), int2 (MPCB aux + contactor aux, internal),
# field (two terminals at -X2, a field contact). sense = contact symbol NO/NC.
DI = [
    dict(ch=0, tag="ESTOP_OK", desc="E-stop safety relay healthy", kind="int1", devs=["-K0"], pins=["33-34"],
         sense="NO", one="safety OK"),
    dict(ch=1, tag="PB_START", desc="Panel START", kind="field", devs=["-S1"], sense="NO", act="push",
         dtext="START, green", cable="-W90", one="pressed"),
    dict(ch=2, tag="PB_STOP_OK", desc="Panel STOP", kind="field", devs=["-S2"], sense="NC", act="push",
         dtext="STOP, red", cable="-W90", one="not pressed"),
    dict(ch=3, tag="PB_RESET", desc="Panel RESET", kind="field", devs=["-S3"], sense="NO", act="push",
         dtext="RESET, blue", cable="-W90", one="pressed"),
    dict(ch=4, tag="LSL201_OK", desc="LSL-201 T-201 low level", kind="field", devs=["-B202"], sense="NO",
         act="float", dtext="LSL-201 float", cable="-W51", one="water present"),
    dict(ch=5, tag="P201_FB", desc="P-201 running", kind="int2", devs=["-Q201", "-K201"], one="running"),
    dict(ch=6, tag="LSL311_OK", desc="LSL-311 stock A low level", kind="field", devs=["-B311"], sense="NO",
         act="float", dtext="LSL-311 float", cable="-W52", one="not low"),
    dict(ch=7, tag="LSL312_OK", desc="LSL-312 stock B low level", kind="field", devs=["-B312"], sense="NO",
         act="float", dtext="LSL-312 float", cable="-W53", one="not low"),
    dict(ch=8, tag="LSL313_OK", desc="LSL-313 acid low level", kind="field", devs=["-B313"], sense="NO",
         act="float", dtext="LSL-313 float", cable="-W54", one="not low"),
    dict(ch=9, tag="P311_FB", desc="P-311 running (pump run relay)", kind="field", devs=["-M311"], sense="NO",
         act=None, dtext="P-311 run relay", cable="-W31", one="running"),
    dict(ch=10, tag="P312_FB", desc="P-312 running (pump run relay)", kind="field", devs=["-M312"], sense="NO",
         act=None, dtext="P-312 run relay", cable="-W32", one="running"),
    dict(ch=11, tag="P313_FB", desc="P-313 running (pump run relay)", kind="field", devs=["-M313"], sense="NO",
         act=None, dtext="P-313 run relay", cable="-W33", one="running"),
    dict(ch=12, tag="RAIN_DRY", desc="XS-105 rain detector", kind="field", devs=["-B105"], sense="NC",
         act=None, dtext="XS-105 relay", cable="-W55", one="no rain"),
    dict(ch=13, tag="ZSO511", desc="Vent fully open", kind="field", devs=["-B512"], sense="NO", act="limit",
         dtext="ZSO-511 limit", cable="-W56", one="at limit"),
    dict(ch=14, tag="ZSC511", desc="Vent fully closed", kind="field", devs=["-B513"], sense="NO", act="limit",
         dtext="ZSC-511 limit", cable="-W56", one="at limit"),
    dict(ch=15, tag="M511_OK", desc="Vent motor breaker healthy", kind="int1", devs=["-Q511"], pins=["13-14"],
         sense="NO", one="healthy"),
    dict(ch=16, tag="ZSO521", desc="Shade net fully open (retracted)", kind="field", devs=["-B522"], sense="NO",
         act="limit", dtext="ZSO-521 limit", cable="-W57", one="at limit"),
    dict(ch=17, tag="ZSC521", desc="Shade net fully closed (deployed)", kind="field", devs=["-B523"], sense="NO",
         act="limit", dtext="ZSC-521 limit", cable="-W57", one="at limit"),
    dict(ch=18, tag="M521_OK", desc="Net motor breaker healthy", kind="int1", devs=["-Q521"], pins=["13-14"],
         sense="NO", one="healthy"),
    dict(ch=19, tag="F601_FB", desc="F-601 running", kind="int2", devs=["-Q601", "-K601"], one="running"),
    dict(ch=20, tag="F602_FB", desc="F-602 running", kind="int2", devs=["-Q602", "-K602"], one="running"),
    dict(ch=21, tag="F603_FB", desc="F-603 running", kind="int2", devs=["-Q603", "-K603"], one="running"),
    dict(ch=22, tag="P531_FB", desc="P-531 pad pump running", kind="int2", devs=["-Q531", "-K531"], one="running"),
    dict(ch=23, tag="LSL531_OK", desc="LSL-531 pad sump low level", kind="field", devs=["-B531"], sense="NO",
         act="float", dtext="LSL-531 float", cable="-W58", one="water present"),
    dict(ch=24, tag="P541_FB", desc="P-541 fog pump running", kind="int2", devs=["-Q541", "-K541"], one="running"),
]

# Digital outputs. load: sol (field solenoid at -X2), coil (internal contactor coil),
# coil_sw (coil through a field switch at -X2, e.g. limit or pressure switch), lamp.
DO = [
    dict(ch=0, tag="XV201", desc="Refill valve XV-201", load="sol", dev="-Y201", cable="-W41"),
    dict(ch=1, tag="P201", desc="Irrigation pump P-201", load="coil", dev="-K201"),
    dict(ch=2, tag="XV301", desc="Return valve XV-301", load="sol", dev="-Y301", cable="-W42"),
    dict(ch=3, tag="XV401", desc="Zone 1 valve XV-401", load="sol", dev="-Y401", cable="-W43"),
    dict(ch=4, tag="XV402", desc="Zone 2 valve XV-402", load="sol", dev="-Y402", cable="-W44"),
    dict(ch=5, tag="XV403", desc="Zone 3 valve XV-403", load="sol", dev="-Y403", cable="-W45"),
    dict(ch=6, tag="XV404", desc="Zone 4 valve XV-404", load="sol", dev="-Y404", cable="-W46"),
    dict(ch=7, tag="P311", desc="Dosing pump A run", load="coil", dev="-K311"),
    dict(ch=8, tag="P312", desc="Dosing pump B run", load="coil", dev="-K312"),
    dict(ch=9, tag="P313", desc="Acid pump run", load="coil", dev="-K313"),
    dict(ch=10, tag="M511_OPEN", desc="Vent motor, open", load="coil_sw", dev="-K511.1", sw="-B512",
         swtext="ZSO-511 NC end limit", ilk="-K511.2", cable="-W56"),
    dict(ch=11, tag="M511_CLOSE", desc="Vent motor, close", load="coil_sw", dev="-K511.2", sw="-B513",
         swtext="ZSC-511 NC end limit", ilk="-K511.1", cable="-W56"),
    dict(ch=12, tag="M521_OPEN", desc="Net motor, retract", load="coil_sw", dev="-K521.1", sw="-B522",
         swtext="ZSO-521 NC end limit", ilk="-K521.2", cable="-W57"),
    dict(ch=13, tag="M521_CLOSE", desc="Net motor, deploy", load="coil_sw", dev="-K521.2", sw="-B523",
         swtext="ZSC-521 NC end limit", ilk="-K521.1", cable="-W57"),
    dict(ch=14, tag="F601", desc="Exhaust fan F-601", load="coil", dev="-K601"),
    dict(ch=15, tag="F602", desc="Exhaust fan F-602", load="coil", dev="-K602"),
    dict(ch=16, tag="F603", desc="Exhaust fan F-603", load="coil", dev="-K603"),
    dict(ch=17, tag="P531", desc="Pad pump P-531", load="coil", dev="-K531"),
    dict(ch=18, tag="P541", desc="Fog pump P-541", load="coil_sw", dev="-K541", sw="-B541",
         swtext="PSL-541 inlet pressure OK", ilk=None, cable="-W59", swkind="NO"),
    dict(ch=19, tag="LAMP_GREEN", desc="Stack light green", load="lamp", dev="-P1.1", colour="GN"),
    dict(ch=20, tag="LAMP_AMBER", desc="Stack light amber", load="lamp", dev="-P1.2", colour="YE"),
    dict(ch=21, tag="LAMP_RED", desc="Stack light red", load="lamp", dev="-P1.3", colour="RD"),
]

# Analog inputs. wiring: 2w (loop-powered from the module) or 4w (active output, own supply).
AI = [
    dict(ch=0, tag="LT201_RAW", isa="LT-201", desc="T-201 level", dev="-B201", wiring="2w", rng=(0, 100, "%"),
         alarm="A20", what="hydrostatic level transmitter"),
    dict(ch=1, tag="FT201_RAW", isa="FT-201", desc="Main line flow", dev="-B203", wiring="4w", rng=(0, 6000, "L/h"),
         alarm="A21", what="magnetic flowmeter, 24 V DC powered"),
    dict(ch=2, tag="PT201_RAW", isa="PT-201", desc="Main line pressure", dev="-B204", wiring="2w",
         rng=(0, 6.0, "bar"), alarm="A22", what="pressure transmitter"),
    dict(ch=3, tag="AIT301_RAW", isa="AIT-301", desc="EC", dev="-B301", wiring="4w", rng=(0, 5.0, "mS/cm"),
         alarm="A23", what="conductivity analyser, 230 V powered"),
    dict(ch=4, tag="AIT302_RAW", isa="AIT-302", desc="pH probe A", dev="-B302", wiring="4w", rng=(0, 14, "pH"),
         alarm="A24", what="pH analyser, 230 V powered"),
    dict(ch=5, tag="AIT303_RAW", isa="AIT-303", desc="pH probe B", dev="-B303", wiring="4w", rng=(0, 14, "pH"),
         alarm="A25", what="pH analyser, 230 V powered"),
    dict(ch=6, tag="FT402_RAW", isa="FT-402", desc="Z1 drain flow", dev="-B402", wiring="2w", rng=(0, 200, "L/h"),
         alarm="A27", what="drain gutter flow transmitter"),
    dict(ch=7, tag="RT101_RAW", isa="RT-101", desc="Global radiation", dev="-B101", wiring="2w",
         rng=(0, 1500, "W/m²"), alarm="A29", what="pyranometer with 4-20 mA converter"),
    dict(ch=8, tag="TT101_RAW", isa="TT-101", desc="Outside temperature", dev="-B102", wiring="2w",
         rng=(0, 50, "°C"), alarm="A31", what="combined T/RH sensor, channel T"),
    dict(ch=9, tag="MT101_RAW", isa="MT-101", desc="Outside humidity", dev="-B102", wiring="2w",
         rng=(0, 100, "%RH"), alarm="A31", what="combined T/RH sensor, channel RH"),
    dict(ch=10, tag="ST101_RAW", isa="ST-101", desc="Wind speed", dev="-B104", wiring="2w", rng=(0, 40, "m/s"),
         alarm="A30", what="cup anemometer"),
    dict(ch=11, tag="TT501_RAW", isa="TT-501", desc="Greenhouse temperature", dev="-B501", wiring="2w",
         rng=(0, 50, "°C"), alarm="A32", what="aspirated T/RH box, channel T"),
    dict(ch=12, tag="MT501_RAW", isa="MT-501", desc="Greenhouse humidity", dev="-B501", wiring="2w",
         rng=(0, 100, "%RH"), alarm="A33", what="aspirated T/RH box, channel RH"),
    dict(ch=13, tag="AT502_RAW", isa="AT-502", desc="Greenhouse CO2", dev="-B502", wiring="4w",
         rng=(0, 2000, "ppm"), alarm="A34", what="NDIR CO2 transmitter, 24 V DC powered"),
    dict(ch=14, tag="ZT511_RAW", isa="ZT-511", desc="Vent position", dev="-B511", wiring="2w", rng=(0, 100, "%"),
         alarm="A35", what="position transmitter on the vent drive"),
]
AO = [dict(ch=d[10], tag=f"{d[3].replace('-', '')}_REF", desc=f"{d[3]} speed reference", dev=d[0], cable=d[7],
           pump=d[3]) for d in DOSING]

# --------------------------------------------------------------------------- devices (parts list)
DEVICES = [
    ("-Q0", "Main switch-disconnector 4P 40 A AC-23A, lockable red/yellow handle", "Door"),
    ("-X0", "PE bar, copper, with removable 0V-PE link", "Panel"),
    ("-X1", "Terminals 230/400 V AC incoming + panel fan", "Panel"),
    ("-F1", "MCB 1P+N C6 A - 24 V DC power supply", "Panel"),
    ("-F2", "MCB 1P+N C2 A - panel fan", "Panel"),
    ("-F3", "MCB 1P+N C10 A - dosing pumps 230 V, RCD 30 mA type A", "Panel"),
    ("-F4", "MCB 1P+N C6 A - analysers 230 V (AIT-301...303)", "Panel"),
    ("-B1", "Panel thermostat NO, set 35 °C", "Panel"),
    ("-E1", "Filter fan 230 V AC + outlet filter", "Door"),
    ("-G1", "Power supply 230 V AC / 24 V DC 10 A", "Panel"),
    ("-F21", "DC MCB 1P 4 A - +24.1 coupler, PLC, switch", "Panel"),
    ("-F22", "DC MCB 1P 2 A - +24.2 digital inputs", "Panel"),
    ("-F23", "DC MCB 1P 2 A - +24.3 stack light amber/red", "Panel"),
    ("-F24", "DC MCB 1P 4 A - +24.4 analog loops, 24 V instruments", "Panel"),
    ("-F25", "DC MCB 1P 6 A - +24.5 safety relay, source of 24V-S", "Panel"),
    ("-K0", "Safety relay, 2-ch. E-stop, monitored reset, 3 NO + 1 NC, 24 V DC", "Panel"),
]
for m, q, k, tag, desc, kw, i_n, rng, *_ in DOL:
    DEVICES += [(q, f"Motor-protection circuit breaker {rng}, aux 1 NO - {tag}", "Panel"),
                (k, f"Contactor 3P AC-3 9 A, coil 24 V DC, aux 1 NO + 1 NC - {tag}", "Panel")]
for m, q, k1, k2, tag, desc, kw, i_n, rng, *_ in REV_DRIVES:
    DEVICES += [(q, f"Motor-protection circuit breaker {rng}, aux 1 NO - {tag}", "Panel"),
                (k1, f"Contactor 3P 9 A, coil 24 V DC, mech. interlock - {tag} open", "Panel"),
                (k2, f"Contactor 3P 9 A, coil 24 V DC, mech. interlock - {tag} close", "Panel")]
for m, f, k, tag, *_ in DOSING:
    DEVICES += [(f, f"MCB 1P+N C2 A, aux 1 NO - {tag}", "Panel"),
                (k, f"Contactor 2P 230 V AC-3 9 A, coil 24 V DC - {tag}", "Panel")]
DEVICES += [
    ("-A10", "PLC: industrial PC, OpenPLC Runtime v4 (Linux, Docker)", "Panel"),
    ("-A11", "Ethernet switch, managed, 8 ports, 24 V DC", "Panel"),
    ("-A1", "Remote I/O coupler, Modbus TCP, NTP clock, 24 V DC", "Panel"),
    ("-A1.1", "Digital input module DI16, 24 V DC, sinking", "Panel"),
    ("-A1.2", "Digital input module DI16, 24 V DC, sinking", "Panel"),
    ("-A1.3", "Digital output module DO16, 24 V DC 0.5 A, 2 supply groups", "Panel"),
    ("-A1.4", "Digital output module DO8, 24 V DC 0.5 A, 2 supply groups", "Panel"),
    ("-A1.5", "Analog input module AI8, 4-20 mA, loop supply", "Panel"),
    ("-A1.6", "Analog input module AI8, 4-20 mA, loop supply", "Panel"),
    ("-A1.7", "Analog output module AO4, 4-20 mA", "Panel"),
    ("-X2", "Terminals 24 V DC digital and safety, spring clamp 2.5 mm²", "Panel"),
    ("-X3", "Terminals analog, with shield clamps", "Panel"),
    ("-X4", "Terminals motor and pump outgoing, 4 mm²", "Panel"),
    ("-S0.1", "E-stop, red mushroom, 2 NC positive opening - panel door", "Door"),
    ("-S0.2", "E-stop, red mushroom, 2 NC positive opening, IP65 box - fertigation skid", "Field"),
    ("-S0R", "Push-button blue NO - safety reset", "Door"),
    ("-S1", "Push-button green NO - START", "Door"),
    ("-S2", "Push-button red NC - STOP", "Door"),
    ("-S3", "Push-button blue NO - RESET", "Door"),
    ("-P1", "Stack light GN/YE/RD, 24 V DC LED", "Roof"),
    ("-A12", "HMI PC (web browser), office", "Office"),
    ("-A13", "Router / firewall, farm network and remote access (VPN)", "Office"),
]
for m, q, k, tag, desc, kw, i_n, *_ in DOL:
    DEVICES.append((m, f"{tag} {desc.lower()}, {kw} kW 400 V {i_n} A", "Field"))
for m, q, k1, k2, tag, desc, kw, i_n, *_ in REV_DRIVES:
    DEVICES.append((m, f"{tag} {desc.lower()}, {kw} kW 400 V, gear motor", "Field"))
for m, f, k, tag, desc, *_ in DOSING:
    DEVICES.append((m, f"{tag} {desc}, 230 V, 4-20 mA speed in, run relay out", "Field"))
DEVICES += [
    ("-Y201", "XV-201 refill solenoid valve 24 V DC, NC", "Field"),
    ("-Y301", "XV-301 return solenoid valve 24 V DC, NC", "Field"),
    ("-Y401", "XV-401 zone 1 solenoid valve 24 V DC, NC", "Field"),
    ("-Y402", "XV-402 zone 2 solenoid valve 24 V DC, NC", "Field"),
    ("-Y403", "XV-403 zone 3 solenoid valve 24 V DC, NC", "Field"),
    ("-Y404", "XV-404 zone 4 solenoid valve 24 V DC, NC", "Field"),
    ("-B105", "XS-105 rain detector, relay output NC (opens on rain)", "Field"),
    ("-B202", "LSL-201 T-201 low-level float switch", "Field"),
    ("-B311", "LSL-311 stock A low-level float switch", "Field"),
    ("-B312", "LSL-312 stock B low-level float switch", "Field"),
    ("-B313", "LSL-313 acid low-level float switch (PVDF)", "Field"),
    ("-B512", "ZSO-511 vent open limit switch, 1 NO + 1 NC", "Field"),
    ("-B513", "ZSC-511 vent closed limit switch, 1 NO + 1 NC", "Field"),
    ("-B522", "ZSO-521 net retracted limit switch, 1 NO + 1 NC", "Field"),
    ("-B523", "ZSC-521 net deployed limit switch, 1 NO + 1 NC", "Field"),
    ("-B531", "LSL-531 pad sump low-level float switch", "Field"),
    ("-B541", "PSL-541 fog pump inlet pressure switch, NO (closed = pressure OK)", "Field"),
]
_seen = set()
for d in AI:
    if d["dev"] not in _seen:
        _seen.add(d["dev"])
        DEVICES.append((d["dev"], f"{d['isa']} {d['what']}", "Field"))

# --------------------------------------------------------------------------- cables
CABLES = {
    "-W1": "5G10 mm², supply from farm LV board",
    "-W11": "4G1.5 mm², P-201", "-W12": "4G1.5 mm², P-531", "-W13": "4G2.5 mm², P-541",
    "-W14": "4G1.5 mm², F-601", "-W15": "4G1.5 mm², F-602", "-W16": "4G1.5 mm², F-603",
    "-W17": "4G1.5 mm², M-511", "-W18": "4G1.5 mm², M-521",
    "-W21": "3G1.5 mm², P-311", "-W22": "3G1.5 mm², P-312", "-W23": "3G1.5 mm², P-313",
    "-W31": "LiYCY 4x0.75 mm², P-311 control", "-W32": "LiYCY 4x0.75 mm², P-312 control",
    "-W33": "LiYCY 4x0.75 mm², P-313 control",
    "-W41": "2x0.75 mm², XV-201", "-W42": "2x0.75 mm², XV-301", "-W43": "2x0.75 mm², XV-401",
    "-W44": "2x0.75 mm², XV-402", "-W45": "2x0.75 mm², XV-403", "-W46": "2x0.75 mm², XV-404",
    "-W51": "2x0.75 mm², LSL-201", "-W52": "2x0.75 mm², LSL-311", "-W53": "2x0.75 mm², LSL-312",
    "-W54": "2x0.75 mm², LSL-313", "-W55": "2x0.75 mm², XS-105", "-W56": "8x0.75 mm², vent limits",
    "-W57": "8x0.75 mm², net limits", "-W58": "2x0.75 mm², LSL-531", "-W59": "2x0.75 mm², PSL-541",
    "-W90": "door loom H05V-K 0.75 mm²", "-W91": "5x0.75 mm², stack light", "-W92": "3G1.0 mm², door fan",
    "-W93": "4x0.75 mm² + screen, E-stop -S0.2",
    "-W501": "Cat 6A S/FTP, -A10 to -A11", "-W502": "Cat 6A S/FTP, -A1 to -A11",
    "-W503": "Cat 6A S/FTP, -A11 to -A13 (office link)",
}
for i, d in enumerate(AI):
    CABLES[f"-W{61 + i}"] = f"LiYCY 2x0.75 mm² shielded, {d['isa']}"
    d["cable"] = f"-W{61 + i}"


def contacts_of(dev: str) -> list[tuple[str, str, str]]:
    """Contacts of a coil-operated device, for contact mirrors: (t1, t2, kind)."""
    if dev in [d[2] for d in DOL]:
        return [("1", "2", "NO"), ("3", "4", "NO"), ("5", "6", "NO"), ("13", "14", "NO"), ("21", "22", "NC")]
    if any(dev in (d[2], d[3]) for d in REV_DRIVES):
        return [("1", "2", "NO"), ("3", "4", "NO"), ("5", "6", "NO"), ("21", "22", "NC")]
    if dev in [d[2] for d in DOSING]:
        return [("1", "2", "NO"), ("3", "4", "NO")]
    return []
