#!/usr/bin/env python3
"""GH-1 Tropical Greenhouse - electrical drawing generator.

Generates the electrical drawing set, the terminal plans, the parts list and the I/O
checkout sheet from one data model (gh1_data.py), so they always agree.

    python tools/drawings/make_drawings.py

Outputs (overwritten on every run)
    docs/drawings/GH1-E-00.svg ... GH1-E-14.svg   A3 landscape sheets
    docs/drawings/index.html                       all sheets, print-ready
    docs/drawings/README.md                        sheet list and conventions
    docs/IO_CHECKOUT.md                            I/O loop-check sheet

Python 3.10+, standard library only. Cross-references are resolved in two passes:
pass 1 draws every sheet and records where each device, contact and terminal is
placed (sheet and column); pass 2 draws again and prints the references.
The drawing engine (engine.py) comes from plc-batch-station (T-101).
"""
from __future__ import annotations

import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import engine as E  # noqa: E402
from engine import (BUS, GREY, LW, THIN, Sheet, arrow, boxed, bus_in, coil, contact, frame,  # noqa: E402
                    lamp, motor, notes, pe_sym, poles, prot_boxes, psu_box, reg, suppressor, table, term,
                    tw, wn, xr, zero_v)
import gh1_data as D  # noqa: E402

OUT_DIR = ROOT / "docs" / "drawings"
CHECKOUT_MD = ROOT / "docs" / "IO_CHECKOUT.md"

E.CFG.PROJECT, E.CFG.DOC_PREFIX, E.CFG.REV, E.CFG.DATE = D.PROJECT, D.DOC_PREFIX, D.REV, D.DATE
E.CFG.SHEETS, E.CFG.SUBTITLE, E.CFG.SET_TITLE, E.CFG.SCALED = D.SHEETS, D.SUBTITLE, D.SET_TITLE, D.SCALED

# =============================================================================
# TERMINAL ASSIGNMENT (derived from the data, so the plan cannot drift)
# =============================================================================
X2 = {}            # (kind, key) -> terminal numbers
_n = 11
for d in D.DI:
    if d["kind"] == "field":
        d["terms"] = (str(_n), str(_n + 1))          # (supply, signal)
        _n += 2
_n = 101
for d in D.DO:
    if d["load"] in ("sol", "coil_sw"):
        d["terms"] = (str(_n), str(_n + 1))          # (signal out, return)
        _n += 2
LAMP_TERMS = {19: "131", 20: "132", 21: "133"}
LAMP_COMMON = "134"
for i, d in enumerate(D.AI):
    d["terms"] = (str(3 * i + 1), str(3 * i + 2), str(3 * i + 3))
for i, d in enumerate(D.AO):
    d["terms"] = (str(51 + 3 * i), str(52 + 3 * i), str(53 + 3 * i))

DI_WIRE = {d["ch"]: f"7{d['ch'] + 1:02d}" for d in D.DI}
DO_WIRE = {d["ch"]: f"8{d['ch'] + 1:02d}" for d in D.DO}
AI_WIRE = {d["ch"]: (f"9{2 * d['ch'] + 1:02d}", f"9{2 * d['ch'] + 2:02d}") for d in D.AI}


def build_terminals() -> list[tuple]:
    """(strip, terminal, wire, panel side, field side, cable, function)."""
    T = [("X1", "1", "L1", "-Q0:1", "supply L1", "-W1", "Incoming L1 (live with -Q0 open)"),
         ("X1", "2", "L2", "-Q0:3", "supply L2", "-W1", "Incoming L2 (live with -Q0 open)"),
         ("X1", "3", "L3", "-Q0:5", "supply L3", "-W1", "Incoming L3 (live with -Q0 open)"),
         ("X1", "4", "N", "-Q0:7", "supply N", "-W1", "Incoming N"),
         ("X1", "5", "PE", "-X0 PE bar", "supply PE", "-W1", "Incoming PE"),
         ("X1", "6", "104", "-B1:14", "-E1:L", "-W92", "Filter fan L (thermostat switched)"),
         ("X1", "7", "105", "-F2:4 (N)", "-E1:N", "-W92", "Filter fan N"),
         ("X1", "8", "PE", "-X0 PE bar", "-E1:PE", "-W92", "Filter fan PE"),
         ("X2", "1", "601", "-K0:S11", "-S0.1:11", "-W90", "E-stop ch. 1, to door -S0.1"),
         ("X2", "2", "602", "-S0.1:12", "-S0.2:11", "-W93", "E-stop ch. 1, door to field -S0.2"),
         ("X2", "3", "603", "-K0:S12", "-S0.2:12", "-W93", "E-stop ch. 1 return"),
         ("X2", "4", "604", "-K0:S21", "-S0.1:21", "-W90", "E-stop ch. 2, to door -S0.1"),
         ("X2", "5", "605", "-S0.1:22", "-S0.2:21", "-W93", "E-stop ch. 2, door to field -S0.2"),
         ("X2", "6", "606", "-K0:S22", "-S0.2:22", "-W93", "E-stop ch. 2 return"),
         ("X2", "7", "607", "-K0:S33", "-S0R:13", "-W90", "Safety reset out"),
         ("X2", "8", "608", "-K201:21", "-S0R:14", "-W90", "Safety reset return to the EDM loop")]
    for d in D.DI:
        if d["kind"] == "field":
            a, b = d["terms"]
            T.append(("X2", a, "+24.2", "bridge +24.2", f"{d['devs'][0]}:1", d["cable"], f"{d['tag']} supply"))
            T.append(("X2", b, DI_WIRE[d["ch"]], f"-A1.{1 if d['ch'] < 16 else 2}:DI{d['ch'] % 16}",
                      f"{d['devs'][0]}:2", d["cable"], f"{d['tag']}  %IX{100 + d['ch'] // 8}.{d['ch'] % 8}"))
    for d in D.DO:
        if d["load"] == "sol":
            a, b = d["terms"]
            T.append(("X2", a, DO_WIRE[d["ch"]], f"-A1.{3 if d['ch'] < 16 else 4}:DO{d['ch'] % 16}",
                      f"{d['dev']}:1", d["cable"], f"{d['tag']}  %QX{100 + d['ch'] // 8}.{d['ch'] % 8} (24V-S)"))
            T.append(("X2", b, "0V", "bridge 0V", f"{d['dev']}:2", d["cable"], f"{d['dev']} solenoid 0 V"))
        elif d["load"] == "coil_sw":
            a, b = d["terms"]
            T.append(("X2", a, DO_WIRE[d["ch"]], f"-A1.{3 if d['ch'] < 16 else 4}:DO{d['ch'] % 16}",
                      f"{d['sw']}:1", d["cable"], f"{d['tag']} via {d['swtext']}"))
            T.append(("X2", b, f"8{d['ch'] + 31:02d}", f"{d['ilk'] or d['dev']}:{'21' if d['ilk'] else 'A1'}",
                      f"{d['sw']}:2", d["cable"], f"{d['dev']} coil circuit return"))
    for ch, t in LAMP_TERMS.items():
        d = D.DO[ch]
        T.append(("X2", t, DO_WIRE[ch], f"-A1.4:DO{ch % 16}", f"{d['dev']} ({d['colour']})", "-W91",
                  f"{d['tag']}  %QX{100 + ch // 8}.{ch % 8}"))
    T.append(("X2", LAMP_COMMON, "0V", "bridge 0V", "-P1:N", "-W91", "Stack light 0 V common"))
    for d in D.AI:
        p, m, sh = d["terms"]
        w1, w2 = AI_WIRE[d["ch"]]
        mod = f"-A1.{5 if d['ch'] < 8 else 6}"
        if d["wiring"] == "2w":
            T.append(("X3", p, w1, f"{mod}:+24V{d['ch'] % 8}", f"{d['dev']}:+", d["cable"], f"{d['isa']} loop supply (+)"))
            T.append(("X3", m, w2, f"{mod}:AI{d['ch'] % 8}", f"{d['dev']}:-", d["cable"],
                      f"{d['isa']} signal  %IW{100 + d['ch']}"))
        else:
            T.append(("X3", p, w1, f"{mod}:AI{d['ch'] % 8}", f"{d['dev']}:I+", d["cable"],
                      f"{d['isa']} signal  %IW{100 + d['ch']} (active)"))
            T.append(("X3", m, w2, f"{mod}:M{d['ch'] % 8}", f"{d['dev']}:I-", d["cable"], f"{d['isa']} signal return"))
        T.append(("X3", sh, "SH", "shield clamp", f"{d['cable']} shield", d["cable"], "Shield, earthed in the panel only"))
    for i, d in enumerate(D.AO):
        p, m, sh = d["terms"]
        T.append(("X3", p, f"5{31 + 2 * i}", f"-A1.7:AO{d['ch']}+", f"{d['dev']}:AI+", d["cable"],
                  f"{d['pump']} speed  %QW{100 + d['ch']}"))
        T.append(("X3", m, f"5{32 + 2 * i}", f"-A1.7:AO{d['ch']}-", f"{d['dev']}:AI-", d["cable"], f"{d['pump']} speed return"))
        T.append(("X3", sh, "SH", "shield clamp", f"{d['cable']} shield", d["cable"], "Shield, earthed in the panel only"))
    for f in D.DOL:
        m, q, k, tag, _desc, *_r = f
        t0, cable = f[9], f[8]
        sheet = "2" if tag.startswith("P") else "3"
        idx = [x[0] for x in D.DOL if (x[3].startswith("P") == tag.startswith("P"))].index(m)
        for j, ph in enumerate(("U", "V", "W")):
            T.append(("X4", str(t0 + j), f"{sheet}{10 * idx + 4 + j:02d}", f"{k}:{2 * j + 2}", f"{m}:{ph}1", cable,
                      f"{tag} {ph}"))
        T.append(("X4", str(t0 + 3), "PE", "-X0 PE bar", f"{m}:PE", cable, f"{tag} PE"))
    for i, f in enumerate(D.REV_DRIVES):
        m, q, k1, k2, tag = f[:5]
        t0, cable = f[10], f[9]
        for j, ph in enumerate(("U", "V", "W")):
            T.append(("X4", str(t0 + j), f"4{20 * i + 10 + j:02d}", f"{k1}:{2 * j + 2}", f"{m}:{ph}1", cable,
                      f"{tag} {ph}"))
        T.append(("X4", str(t0 + 3), "PE", "-X0 PE bar", f"{m}:PE", cable, f"{tag} PE"))
    for i, f in enumerate(D.DOSING):
        m, mcb, k, tag, _desc, cable, t0 = f[:7]
        T.append(("X4", str(t0), f"5{10 * i + 5:02d}", f"{k}:2", f"{m}:L", cable, f"{tag} L"))
        T.append(("X4", str(t0 + 1), f"5{10 * i + 6:02d}", f"{k}:4", f"{m}:N", cable, f"{tag} N"))
        T.append(("X4", str(t0 + 2), "PE", "-X0 PE bar", f"{m}:PE", cable, f"{tag} PE"))
    return T


TERMINALS = build_terminals()
TERM = {(t[0], t[1]): t for t in TERMINALS}


# =============================================================================
# EXTRA SYMBOLS
# =============================================================================
def hcontact(s, x, y, kind="NO", L=10.0, act=None):
    """Contact in a horizontal conductor, terminals at (x, y) and (x+L, y)."""
    a, b = x + L * 0.32, x + L * 0.68
    s.line(x, y, a, y, LW)
    s.line(b, y, x + L, y, LW)
    if kind == "NO":
        s.line(b, y, a, y + 2.3, LW)
        mx, my = (a + b) / 2, y + 1.15
    else:
        s.line(a, y, a, y - 2.2, LW)
        s.line(b, y, a - 0.6, y - 2.6, LW)
        mx, my = (a + b) / 2 - 0.3, y - 1.3
    if act == "push":
        s.line(mx, my, mx, y + 3.4, THIN, dash="0.7 0.5")
        s.line(mx - 1.2, y + 3.4, mx + 1.2, y + 3.4, LW)
    elif act == "float":
        s.line(mx, my, mx, y + 2.6, THIN, dash="0.7 0.5")
        s.circle(mx, y + 3.4, 0.8, sw=THIN)
    elif act == "limit":
        s.line(mx, my, mx, y + 2.6, THIN, dash="0.7 0.5")
        s.circle(mx, y + 3.4, 0.8, sw=THIN)
        s.line(mx - 1.4, y + 4.2, mx + 1.4, y + 4.2, THIN)
    elif act == "pressure":
        s.line(mx, my, mx, y + 2.4, THIN, dash="0.7 0.5")
        s.rect(mx - 1.2, y + 2.4, 2.4, 1.6, sw=THIN)
        s.text(mx, y + 3.75, "p", 1.3, anchor="middle")


def hcoil(s, x, y, w=8.0, h=4.4):
    """Coil in a horizontal conductor, body from x to x+w."""
    s.rect(x, y - h / 2, w, h, sw=LW, fill="#fff")


def hterm(s, x, y, strip, num):
    s.circle(x, y, 0.8, sw=THIN, fill="#fff")
    reg(s, strip, num, x)
    s.text(x, y - 1.4, f"{strip}:{num}", 1.45, anchor="middle")


def motor1(s, x, cy, r=7.0):
    motor(s, x, cy, r, "M", "1~")


# =============================================================================
# SHEETS
# =============================================================================
def sheet_e00(s: Sheet):
    t = s.text
    t(22, 31, D.PROJECT, 7.5, bold=True)
    t(22, 40, "Electrical drawing set", 5.0)
    info = [
        "Irrigation (4 drip zones), fertigation (A/B + acid on EC/pH) and climate control, 1 000 m² greenhouse",
        "Supply 3/N/PE AC 400/230 V 50 Hz (TN-S) · control 24 V DC (PELV)",
        "PLC: OpenPLC Runtime v4 (IEC 61131-3 ST) · remote I/O -A1 over Modbus TCP",
        f"Revision {D.REV} · {D.DATE} · first issue for review",
        "Basis: FDS-GH1 §4 (I/O list), §11 (interlocks), §13 (comms loss)",
    ]
    for i, ln in enumerate(info):
        t(22, 47 + i * 4.0, ln, 2.3)
    rows = [["Sheet", "Drawing no.", "Title", "Rev."]]
    for i, (code, title) in enumerate(D.SHEETS):
        rows.append([f"{i + 1} / {len(D.SHEETS)}", D.DOC_PREFIX + code, title, D.REV])
    table(s, 22, 74, [17, 26, 122, 12], rows, size=2.0, rh=4.5, title="Drawing index")
    key = [
        ["Code", "Class (IEC 81346-2)", "Used for"],
        ["A", "Assembly", "-A1 coupler, -A1.1...-A1.7 I/O modules, -A10 PLC, -A11 switch, -A12 HMI"],
        ["B", "Converting a variable into a signal", "-B1 thermostat, -B101...-B541 field instruments"],
        ["E", "Heating / cooling / lighting", "-E1 panel filter fan"],
        ["F", "Protecting", "-F1...-F4, -F21...-F25, -F311...-F313 circuit breakers"],
        ["G", "Supplying energy", "-G1 power supply 24 V DC"],
        ["K", "Processing signals; contactors *", "-K0 safety relay, -K201...-K603 contactors"],
        ["M", "Providing mechanical drive", "-M201 ... -M603 motors and pumps"],
        ["P", "Presenting information", "-P1 stack light (-P1.1 GN, -P1.2 YE, -P1.3 RD)"],
        ["Q", "Switching energy flow", "-Q0 main switch, -Q201...-Q603 motor-protection breakers"],
        ["S", "Manual control", "-S0.1/-S0.2 E-stops, -S0R reset, -S1 START, -S2 STOP, -S3 RESET"],
        ["W", "Guiding (cables)", "-W1 ... -W93, -W501 ... -W503"],
        ["X", "Connecting", "-X0 PE bar, -X1 ... -X4 terminal strips"],
        ["Y", "Electrically operated valve *", "-Y201, -Y301, -Y401 ... -Y404 solenoid valves"],
    ]
    yb = table(s, 22, 157, [12, 52, 124], key, size=1.95, rh=4.4,
               title="Reference designations (product aspect, prefix '-')")
    s.para(22, yb + 4.0,
           "* K for contactors and Y for solenoid valves follow panel-building practice (IEC 81346-2:2019 would "
           "use QA and MB). Feeders and field devices take the P&ID loop number: -K201/-M201 = P-201, "
           "-Y401 = XV-401, -B202 = LSL-201. Sub-devices use a point: -A1.3 = module 3 of -A1, -K511.1 = vent "
           "open contactor.", 188, 1.9)
    x0, y0 = 214, 26
    t(x0, 22, "Symbols (IEC 60617)", 2.6, bold=True)
    cw, chh = 46.5, 23.0
    for i, (cap, fn) in enumerate(LEGEND):
        c, r = i % 4, i // 4
        cx = x0 + c * cw + cw / 2
        cy = y0 + r * chh
        s.rect(x0 + c * cw, cy, cw, chh, sw=0.12)
        fn(s, cx, cy + 3.0)
        t(cx, cy + chh - 1.6, cap, 1.9, anchor="middle")
    yc = y0 + 6 * chh + 6
    t(x0, yc, "Conventions", 2.6, bold=True)
    conv = [
        "Cross-reference /E-08.4 = drawing GH1-E-08, column 4. Contacts point to their coil; on the output "
        "sheet each coil lists where its contacts are drawn.",
        "Wire numbers: potentials keep their name (L1, L2, L3, N, PE, +24.1 ... +24.5, 24V-S, 0V). Other wires "
        "are <sheet><nn>, e.g. 705 = drawn on E-07. A wire keeps its number through a terminal.",
        "Terminals: -X1 230/400 V AC, -X2 24 V DC digital + safety, -X3 analog, -X4 outgoing power, -X0 PE "
        "bar. Terminal plans on E-10 and E-11.",
    ]
    yy = yc + 4.2
    for c in conv:
        yy = s.para(x0, yy, c, 186, 2.0) + 0.6
    colours = [
        ["Circuit", "Wire colour", "Circuit", "Wire colour"],
        ["AC power L1/L2/L3", "black (cores BN/BK/GY)", "+24 V DC (all branches)", "dark blue"],
        ["Neutral N", "light blue", "24V-S safety rail", "dark blue + marker 24V-S"],
        ["Protective earth PE", "green-yellow", "0 V DC", "white-blue"],
        ["230 V AC control", "red", "Analog loops", "shielded twisted pair"],
    ]
    table(s, x0, yy + 5.0, [40, 49, 40, 57], colours, size=1.95, rh=4.6,
          title="Wire colours (IEC 60204-1 §13.2.4, IEC 60445)")


def _lg_limit(s, x, y):
    contact(s, x + 3, y + 1, "NC", 12)
    s.line(x + 1.6, y + 7, x - 4, y + 7, THIN, dash="0.9 0.6")
    s.circle(x - 5.2, y + 7, 1.2, sw=THIN)


def _lg_motor1(s, x, y):
    motor1(s, x, y + 7.5, 6.5)


def _lg_pressure(s, x, y):
    contact(s, x + 3, y + 1, "NO", 12)
    s.line(x + 1.75, y + 7, x - 3, y + 7, THIN, dash="0.9 0.6")
    s.rect(x - 6.4, y + 5.2, 3.4, 3.6, sw=THIN)
    s.text(x - 4.7, y + 7.9, "p", 2.0, anchor="middle")


LEGEND = [
    ("NO contact", E._lg_no), ("NC contact", E._lg_nc), ("Push-button NO", E._lg_pbno),
    ("Push-button NC", E._lg_pbnc), ("E-stop, positive opening", E._lg_estop),
    ("Contactor main contacts", E._lg_cont), ("Circuit breaker I> + thermal", E._lg_brk),
    ("Switch-disconnector", E._lg_swd), ("Coil (relay / contactor / valve)", E._lg_coil),
    ("Coil + suppressor diode", E._lg_coild), ("Signal lamp", E._lg_lamp), ("Motor, 3-phase", E._lg_motor),
    ("Motor, 1-phase", _lg_motor1), ("Power supply AC/DC", E._lg_psu), ("Terminal -X2:11", E._lg_term),
    ("Junction / crossing", E._lg_junction), ("Protective earth PE", E._lg_pe), ("0 V reference", E._lg_0v),
    ("Float switch (level)", E._lg_float), ("Limit switch", _lg_limit), ("Pressure switch", _lg_pressure),
    ("2-wire transmitter", E._lg_tx), ("Shielded cable", E._lg_shield), ("Thermostat", E._lg_thermo),
]


# --- E-01 power distribution --------------------------------------------------
def sheet_e01(s: Sheet):
    t = s.text
    P = [56, 63, 70, 77]
    XPE = 88
    BY = {"L1": 70, "L2": 76, "L3": 82, "N": 88, "PE": 96}
    t(20, 20.5, "Incoming supply", 2.4, bold=True)
    t(20, 24.0, "3/N/PE AC 400/230 V 50 Hz, TN-S", 2.0)
    t(20, 27.2, "-W1 " + D.CABLES["-W1"], 2.0)
    for x, num in zip(P + [XPE], ["1", "2", "3", "4", "5"]):
        s.line(x, 30, x, 34, LW)
        term(s, x, 34.8, "X1", num, side="r", full=False)
    t(54, 35.5, "-X1", 1.9, anchor="end", bold=True)
    poles(s, P, 41, "NO", 14, func="swdisc", act="rotary", terms=[("1", "2"), ("3", "4"), ("5", "6"), ("7", "8")])
    for x in P:
        s.line(x, 35.65, x, 41, LW)
    reg(s, "-Q0", "main", P[0])
    s.label(45.5, 44.5, ["-Q0", "main switch", "4P 40 A", "AC-23A, LOTO"], 1.9)
    for x, b in zip(P, ["L1", "L2", "L3", "N"]):
        s.line(x, 55, x, BY[b], BUS)
    s.line(XPE, 35.65, XPE, BY["PE"], BUS)
    for b in ("L1", "L2", "L3", "PE"):
        x0 = {"L1": 56, "L2": 63, "L3": 70, "PE": XPE}[b]
        s.line(x0, BY[b], 396, BY[b], BUS)
        arrow(s, 398, BY[b], "r")
        t(395, BY[b] - 0.9, b + "  to /E-02, /E-03, /E-04", 1.7, anchor="end")
    reg(s, "L123", "out", 396)
    s.line(77, BY["N"], 330, BY["N"], BUS)
    for b in ("L1", "L2", "L3", "N", "PE"):
        t(98, BY[b] - 0.9, b, 2.0, bold=True)
    t(20, 68, "main conductors 10 mm²", 1.7, color=GREY)

    def mcb2(x, ph, ref, lines, w1, w2):
        s.dot(x, BY[ph]); s.dot(x + 6, BY["N"])
        s.line(x, BY[ph], x, 106, LW); s.line(x + 6, BY["N"], x + 6, 106, LW)
        poles(s, [x, x + 6], 106, "NO", 12, func="breaker", prot=True, terms=[("1", "2"), ("3", "4")])
        reg(s, ref, "main", x)
        s.label(x - 14.5, 108.5, [ref] + lines, 1.9)
        s.line(x, 118, x, 126, LW); s.line(x + 6, 118, x + 6, 126, LW)
        wn(s, x, 123, w1, "l"); wn(s, x + 6, 123, w2, "r")

    # -F1 -> -G1
    mcb2(128, "L1", "-F1", ["C6 A 1P+N", "24 V supply"], "101", "102")
    s.line(128, 126, 128, 132, LW); s.line(134, 126, 134, 132, LW)
    s.dot(146, BY["PE"]); s.line(146, BY["PE"], 146, 132, LW)
    psu_box(s, 118, 132, 38, 22)
    reg(s, "-G1", "main", 128)
    for x, lab in ((128, "L"), (134, "N"), (146, "PE")):
        t(x + 0.8, 130.8, lab, 1.6)
    s.label(114, 138, ["-G1", "230 V AC / 24 V DC", "10 A (240 W)"], 1.9)
    t(125, 157.8, "−", 2.2); t(147, 157.8, "+", 2.2)
    # -F2 -> -B1 -> fan
    mcb2(196, "L2", "-F2", ["C2 A 1P+N", "panel fan"], "103", "105")
    contact(s, 196, 126, "NO", 8, act="temp", t1="13", t2="14")
    reg(s, "-B1", "main", 196)
    s.label(184, 129.5, ["-B1", "35 °C"], 1.9)
    s.line(196, 134, 196, 142, LW); wn(s, 196, 139, "104", "l")
    s.line(202, 126, 202, 142, LW)
    term(s, 196, 142.8, "X1", "6", side="l", full=True)
    term(s, 202, 142.8, "X1", "7", side="r", full=True)
    s.dot(214, BY["PE"]); s.line(214, BY["PE"], 214, 142, LW)
    term(s, 214, 142.8, "X1", "8", side="r", full=True)
    for x in (196, 202, 214):
        s.line(x, 143.65, x, 150, LW)
    s.rect(191, 150, 27, 11, sw=LW, fill="#fff")
    motor(s, 207.5, 155.5, 3.6, "M", "")
    reg(s, "-E1", "main", 204)
    s.label(220, 152.5, ["-E1", "filter fan 230 V", "door, -W92"], 1.9, anchor="start")
    # -F3 dosing pumps, -F4 analysers
    mcb2(262, "L2", "-F3", ["C10 A 1P+N", "RCD 30 mA", "dosing pumps"], "106", "107")
    s.line(262, 126, 262, 136, LW); s.line(268, 126, 268, 136, LW)
    arrow(s, 262, 137.6, "d", 1.4); arrow(s, 268, 137.6, "d", 1.4)
    t(270, 136.0, "L-D / N-D to " + xr("L-D", "in"), 1.75)
    reg(s, "L-D", "out", 262)
    mcb2(316, "L3", "-F4", ["C6 A 1P+N", "analysers"], "108", "109")
    s.line(316, 126, 316, 136, LW); s.line(322, 126, 322, 136, LW)
    arrow(s, 316, 137.6, "d", 1.4); arrow(s, 322, 137.6, "d", 1.4)
    t(324, 134.6, "AIT-301...303", 1.75)
    t(324, 137.6, "230 V supply", 1.75)

    t(110, 20.5, "Supply data", 2.4, bold=True)
    sd = [
        "Rated supply 3/N/PE AC 400/230 V ±10 %, 50 Hz, TN-S. Phase rotation L1-L2-L3 clockwise (check at -X1).",
        "-Q0: 4-pole switch-disconnector 40 A, red/yellow door handle, lockable in OFF (LOTO). "
        "-X1:1...4 stay live with -Q0 open: shrouded, warning label.",
        "Prospective short-circuit current at -X1 to be confirmed by site; assembly SCCR >= PSCC (IEC 61439-1).",
        "Outdoor and wet-area circuits (dosing pumps, analysers) on 30 mA RCD protection; motors fed by "
        "MPCBs, fault protection by automatic disconnection (IEC 60364-4-41).",
    ]
    yy = 24.5
    for ln in sd:
        yy = s.para(110, yy, "• " + ln, 286, 1.9) + 0.4
    rows = [["Ref.", "Consumer", "Rating", "In", "Protection"]]
    tot = 0.0
    for m, q, k, tag, desc, kw, i_n, rng, *_ in D.DOL:
        rows.append([m, f"{tag} {desc}", f"{kw} kW", f"{i_n} A", f"{q} {rng}"])
        tot += i_n
    for m, q, k1, k2, tag, desc, kw, i_n, rng, *_ in D.REV_DRIVES:
        rows.append([m, f"{tag} {desc}", f"{kw} kW", f"{i_n} A", f"{q} {rng}"])
        tot += i_n
    rows += [["-M311..313", "Dosing pumps (L2)", "3x 40 W", "0.6 A", "-F311...313, -F3"],
             ["-G1", "24 V DC supply (L1)", "0.27 kVA", "1.3 A", "-F1 C6 A"],
             ["", "Total (sum of In, all phases)", "≈ 7.6 kW", f"≈ {tot + 2.6:.0f} A", "-Q0 40 A"]]
    table(s, 236, 152, [17, 49, 17, 14, 52], rows, size=1.8, rh=4.2, title="Load summary")

    s.line(124, 154, 124, 232, BUS)        # 0V
    s.line(146, 154, 146, 184, BUS)        # +24
    s.line(146, 184, 232, 184, BUS)
    t(150, 182.6, "+24 V DC (unfused)", 1.8, bold=True)
    t(122.5, 200, "0V", 1.9, bold=True, anchor="end")
    feeds = [
        ("-F21", 156, "4 A", "+24.1", ["coupler -A1, PLC", "-A10, switch -A11"], ("-A1", "net")),
        ("-F22", 174, "2 A", "+24.2", ["digital inputs"], ("+24.2", "load")),
        ("-F23", 192, "2 A", "+24.3", ["lamps YE/RD"], ("+24.3", "load")),
        ("-F24", 210, "4 A", "+24.4", ["analog loops"], ("+24.4", "load")),
        ("-F25", 228, "6 A", "+24.5", ["safety relay,", "source of 24V-S"], ("+24.5", "load")),
    ]
    for i, (ref, x, rating, pot, desc, target) in enumerate(feeds):
        s.dot(x, 184)
        s.line(x, 184, x, 190, LW)
        contact(s, x, 190, "NO", 10, func="breaker")
        reg(s, ref, "main", x)
        t(x - 1.2, 194.5, ref, 1.75, anchor="end", bold=True)
        t(x - 1.2, 197.5, rating, 1.6, anchor="end")
        s.line(x, 200, x, 204 + 5.2 * i, LW)
        arrow(s, x, 205.4 + 5.2 * i, "d", 1.3)
        t(x + 1.6, 204.4 + 5.2 * i, f"{pot}  {' '.join(desc)}  {xr(*target)}", 1.7)
    boxed(s, 300, 212, 96, 17, [
        "24V-S safety rail: +24.5 switched by -K0 13-14 + 23-24 " + xr("-K0", "13-14"),
        "-> DO supply groups -A1.3 and -A1.4 group A " + xr("24V-S", "do"),
        "Coils and solenoids lose power on E-stop, independently",
        "of the PLC (stop category 0).",
    ], size=1.75, dash="1.2 0.8")
    s.line(40, 232, 396, 232, BUS)
    arrow(s, 398, 232, "r")
    t(395, 230.9, "0V  to /E-05, /E-06, /E-07, /E-08, /E-09", 1.7, anchor="end")
    t(126, 230.9, "0V", 1.9, bold=True)
    s.dot(124, 232)
    s.line(40, 232, 40, 235, LW)
    s.circle(40, 236.2, 1.2, sw=THIN, fill="#fff")
    s.line(39.1, 237.1, 40.9, 235.3, THIN)
    s.line(40, 237.4, 40, 240, LW)
    pe_sym(s, 40, 240)
    reg(s, "-X0", "main", 40)
    t(46, 239.5, "-X0  0V-PE bond (PELV), removable link for insulation test", 1.8)
    t(46, 242.8, "single bonding point; 24 V circuits earthed here only", 1.7, color=GREY)


# --- E-02 / E-03 direct-on-line feeders ---------------------------------------
def bus3(s, x_end, src="/E-01"):
    for b, y in (("L1", 24), ("L2", 29), ("L3", 34), ("PE", 41)):
        s.line(34, y, x_end if b != "PE" else x_end - 6, y, BUS)
        s.text(32.8, y + 0.75, b, 2.0, anchor="end", bold=True)
    s.text(35, 21.5, "from " + src + " (load side of -Q0)", 1.6, color=GREY)


def dol_feeder(s, x0, f, sheet_digit, idx):
    m, q, k, tag, desc, kw, i_n, rng, cable, t0, do_ch, di_ch = f
    xs, xpe = [x0, x0 + 6, x0 + 12], x0 + 24
    t = s.text
    BY = {"L1": 24, "L2": 29, "L3": 34, "PE": 41}
    wbase = f"{sheet_digit}{10 * idx + 1:02d}"
    wires = [f"{sheet_digit}{10 * idx + j:02d}" for j in range(1, 7)]
    for x, b in zip(xs, ("L1", "L2", "L3")):
        s.dot(x, BY[b]); s.line(x, BY[b], x, 50, LW)
    poles(s, xs, 50, "NO", 12, func="breaker", prot=True, terms=[("1", "2"), ("3", "4"), ("5", "6")])
    reg(s, q, "main", xs[1])
    s.label(xs[0] - 15, 49.5, [q, "MPCB " + rng, f"Ir set {i_n} A", "aux 13-14 " + xr(q, "13-14")], 1.9)
    for x, w_ in zip(xs, wires[:3]):
        s.line(x, 62, x, 76, LW); wn(s, x, 69, w_, rot=True)
    poles(s, xs, 76, "NO", 12, func="contactor", terms=[("1", "2"), ("3", "4"), ("5", "6")])
    for (a_, b_), x in zip((("1", "2"), ("3", "4"), ("5", "6")), xs):
        reg(s, k, f"{a_}-{b_}", x)
    s.label(xs[0] - 4.5, 79.5, [k, "coil " + xr(k, "coil"), "AC-3 9 A"], 1.9)
    for x, w_ in zip(xs, wires[3:]):
        s.line(x, 88, x, 154, LW); wn(s, x, 110, w_, rot=True)
    for j, x in enumerate(xs):
        term(s, x, 154.8, "X4", str(t0 + j), side="r", full=False)
    s.dot(xpe, BY["PE"]); s.line(xpe, BY["PE"], xpe, 154, LW)
    term(s, xpe, 154.8, "X4", str(t0 + 3), side="r", full=False)
    t(xs[0] - 2.2, 155.5, "-X4", 1.9, anchor="end", bold=True)
    s.label(xs[0] - 2.2, 164, [cable, D.CABLES[cable].split(",")[0]], 1.8)
    cx, cy, r = xs[1], 188, 8
    for x in xs:
        yy = cy - math.sqrt(r * r - (x - cx) ** 2)
        s.line(x, 155.65, x, yy, LW)
    s.line(xpe, 155.65, xpe, cy, LW); s.line(xpe, cy, cx + r, cy, LW)
    t(cx + r + 1.2, cy - 0.8, "PE", 1.6)
    motor(s, cx, cy, r)
    reg(s, m, "main", cx)
    s.label(cx, 201.5, [m, f"{tag} {desc.lower()}", f"{kw} kW · 400 V · {i_n} A", "direct on line"], 1.9,
            anchor="middle")
    _ = wbase


def mirror_table(s, x, y, devs, title="Contact mirrors"):
    rows = [["Device", "Contacts and where they are drawn"]]
    for dev in devs:
        cells = []
        for t1, t2, kind in D.contacts_of(dev):
            key = f"{t1}-{t2}"
            loc = xr(dev, key) if (dev, key) in E.REG else ("spare" if E.PASS == 2 else "/?")
            cells.append(f"{key} {loc}")
        rows.append([f"{dev} (coil {xr(dev, 'coil')})", "  ".join(cells)])
    return table(s, x, y, [34, 104], rows, size=1.75, rh=4.1, title=title)


def sheet_e02(s: Sheet):
    fs = [f for f in D.DOL if f[3].startswith("P")]
    bus3(s, 300)
    for i, f in enumerate(fs):
        dol_feeder(s, 60 + 98 * i, f, "2", i)
    mirror_table(s, 22, 222, [f[2] for f in fs])
    notes(s, 300, 112, [
        "Coils -K201, -K531, -K541 are switched by the PLC outputs from the safety rail 24V-S (E-08): "
        "an E-stop removes 24V-S and the motors stop, stop category 0.",
        "Running feedback = MPCB aux 13-14 in series with contactor aux 13-14 (E-07): a tripped MPCB also "
        "removes the feedback, so the PLC raises the discrepancy alarm (A04, A43, A45).",
        "P-541 (70 bar fog pump): the inlet pressure switch PSL-541 is in the -K541 coil circuit (E-08), "
        "so the pump stops itself when the clean-water supply fails.",
        "-K201 and -K541 21-22 are in the safety relay's EDM loop (E-06): a welded contactor blocks the reset.",
        "Check motor direction at first start (I/O checkout).",
    ], 100, 1.95)


def sheet_e03(s: Sheet):
    fs = [f for f in D.DOL if f[3].startswith("F")]
    bus3(s, 300)
    for i, f in enumerate(fs):
        dol_feeder(s, 60 + 98 * i, f, "3", i)
    mirror_table(s, 22, 222, [f[2] for f in fs])
    notes(s, 300, 112, [
        "Exhaust fans for pad-and-fan cooling, 48 000 m³/h each, south gable. Staged by the PLC (FDS §8.7); "
        "a locked-out fan is replaced by the next one.",
        "Fans may only run with the roof vents closed. This is a PLC interlock (FDS §11); the vent open "
        "contactor is also blocked while a fan is commanded.",
        "Running feedback = MPCB aux 13-14 in series with contactor aux 13-14 (E-07): A40...A42 on a trip.",
        "Fan guards and belt covers fitted before the first run; check rotation (air out of the house).",
    ], 100, 1.95)


# --- E-04 reversing drives ----------------------------------------------------
def rev_feeder(s, x0, f, idx):
    m, q, k1, k2, tag, desc, kw, i_n, rng, cable, t0, do_o, do_c, di_ok, lim_o, lim_c, verb = f
    t = s.text
    xs = [x0, x0 + 6, x0 + 12]
    xr_ = [x0 + 30, x0 + 36, x0 + 42]
    xpe = x0 + 54
    BY = {"L1": 24, "L2": 29, "L3": 34, "PE": 41}
    w = lambda j: f"4{20 * idx + j:02d}"  # noqa: E731
    for x, b in zip(xs, ("L1", "L2", "L3")):
        s.dot(x, BY[b]); s.line(x, BY[b], x, 50, LW)
    poles(s, xs, 50, "NO", 12, func="breaker", prot=True, terms=[("1", "2"), ("3", "4"), ("5", "6")])
    reg(s, q, "main", xs[1])
    s.label(xs[0] - 15, 49.5, [q, "MPCB " + rng, f"Ir set {i_n} A", "aux 13-14 " + xr(q, "13-14")], 1.9)
    for j, (x, xx, yt) in enumerate(zip(xs, xr_, (66, 69, 72))):
        s.line(x, 62, x, 76, LW)
        s.dot(x, yt); s.line(x, yt, xx, yt, LW); s.line(xx, yt, xx, 76, LW)
        wn(s, x, 64.5, w(j + 1), "l")
    poles(s, xs, 76, "NO", 12, func="contactor", terms=[("1", "2"), ("3", "4"), ("5", "6")])
    poles(s, xr_, 76, "NO", 12, func="contactor", terms=[("1", "2"), ("3", "4"), ("5", "6")])
    for (a_, b_), x, xx in zip((("1", "2"), ("3", "4"), ("5", "6")), xs, xr_):
        reg(s, k1, f"{a_}-{b_}", x)
        reg(s, k2, f"{a_}-{b_}", xx)
    s.label(xs[0] - 4.5, 79.5, [k1, verb.upper(), "coil " + xr(k1, "coil")], 1.9)
    s.label(xr_[2] + 4, 79.5, [k2, "CLOSE" if verb == "open" else "DEPLOY", "coil " + xr(k2, "coil")], 1.9,
            anchor="start")
    s.line(xs[2] + 3, 82, xr_[0] - 3, 82, THIN, dash="0.4 0.6")
    t((xs[2] + xr_[0]) / 2, 80.6, "mech. ilk", 1.4, anchor="middle", color=GREY)
    # reverse contactor crosses L1 and L3
    for xx, yy, xdst in ((xr_[0], 96, xs[2]), (xr_[1], 100, xs[1]), (xr_[2], 104, xs[0])):
        s.line(xx, 88, xx, yy, LW); s.line(xx, yy, xdst, yy, LW); s.dot(xdst, yy)
    for j, x in enumerate(xs):
        s.line(x, 88, x, 154, LW)
        wn(s, x, 128, w(10 + j), rot=True)
        term(s, x, 154.8, "X4", str(t0 + j), side="r", full=False)
    t(x0 + 22, 108.5, "L1 and L3 swapped", 1.6, color=GREY)
    s.dot(xpe, BY["PE"]); s.line(xpe, BY["PE"], xpe, 154, LW)
    term(s, xpe, 154.8, "X4", str(t0 + 3), side="r", full=False)
    t(xs[0] - 2.2, 155.5, "-X4", 1.9, anchor="end", bold=True)
    s.label(xs[0] - 2.2, 164, [cable, D.CABLES[cable].split(",")[0]], 1.8)
    cx, cy, r = xs[1], 188, 8
    for x in xs:
        s.line(x, 155.65, x, cy - math.sqrt(r * r - (x - cx) ** 2), LW)
    s.line(xpe, 155.65, xpe, cy, LW); s.line(xpe, cy, cx + r, cy, LW)
    t(cx + r + 1.2, cy - 0.8, "PE", 1.6)
    motor(s, cx, cy, r)
    reg(s, m, "main", cx)
    s.label(cx, 201.5, [m, f"{tag} {desc.lower()}", f"{kw} kW · 400 V · {i_n} A", "gear motor, reversing"], 1.9,
            anchor="middle")
    t(xpe + 3, 176, f"end limits {lim_o} / {lim_c}:", 1.7)
    t(xpe + 3, 179, "NC in the coil circuits " + xr("lim", f"{lim_o}"), 1.7)
    t(xpe + 3, 182, "NO to the PLC " + xr(lim_o, "main"), 1.7)


def sheet_e04(s: Sheet):
    bus3(s, 300)
    for i, f in enumerate(D.REV_DRIVES):
        rev_feeder(s, 60 + 128 * i, f, i)
    mirror_table(s, 22, 222, [d for f in D.REV_DRIVES for d in (f[2], f[3])])
    notes(s, 316, 112, [
        "Reversing starters: open and close contactors are interlocked mechanically and electrically "
        "(NC 21-22 of each in the other's coil circuit, E-08); the PLC also never commands both.",
        "Each end limit has an NC contact that breaks its own coil circuit directly (hardwired end stop) "
        "and an NO contact to the PLC (ZSO/ZSC, E-07).",
        "The vent position is measured by ZT-511 (E-09); the net only has its end limits.",
        "Motor protection healthy = MPCB aux 13-14 to the PLC (M511_OK, M521_OK): A38 / A39 lock-out.",
    ], 84, 1.95)


# --- E-05 dosing pumps --------------------------------------------------------
def sheet_e05(s: Sheet):
    t = s.text
    for b, y in (("L-D", 24), ("N-D", 29), ("PE", 41)):
        s.line(34, y, 300, y, BUS)
        t(32.8, y + 0.75, b, 2.0, anchor="end", bold=True)
    t(35, 21.5, "from -F3 " + xr("-F3", "main") + " (L2, RCD 30 mA)", 1.6, color=GREY)
    reg(s, "L-D", "in", 34)
    for i, f in enumerate(D.DOSING):
        m, mcb, k, tag, desc, cable, t0, ccable, do_ch, di_ch, ao_ch = f
        x0 = 60 + 82 * i
        xs = [x0, x0 + 6]
        s.dot(xs[0], 24); s.dot(xs[1], 29)
        s.line(xs[0], 24, xs[0], 50, LW); s.line(xs[1], 29, xs[1], 50, LW)
        poles(s, xs, 50, "NO", 12, func="breaker", prot=True, terms=[("1", "2"), ("3", "4")])
        reg(s, mcb, "main", xs[0])
        s.label(xs[0] - 14.5, 52, [mcb, "C2 A 1P+N"], 1.9)
        for j, x in enumerate(xs):
            s.line(x, 62, x, 76, LW); wn(s, x, 69, f"5{10 * i + 1 + j:02d}", rot=True)
        poles(s, xs, 76, "NO", 12, func="contactor", terms=[("1", "2"), ("3", "4")])
        reg(s, k, "1-2", xs[0]); reg(s, k, "3-4", xs[1])
        s.label(xs[0] - 4.5, 79.5, [k, "coil " + xr(k, "coil")], 1.9)
        for j, x in enumerate(xs):
            s.line(x, 88, x, 116, LW); wn(s, x, 102, f"5{10 * i + 5 + j:02d}", rot=True)
            term(s, x, 116.8, "X4", str(t0 + j), side="r", full=False)
        xpe = x0 + 14
        s.dot(xpe, 41); s.line(xpe, 41, xpe, 116, LW)
        term(s, xpe, 116.8, "X4", str(t0 + 2), side="r", full=False)
        t(xs[0] - 2.2, 117.5, "-X4", 1.9, anchor="end", bold=True)
        s.label(xs[0] - 2.2, 126, [cable, D.CABLES[cable].split(",")[0]], 1.8)
        # pump: motor + its electronics (speed input, run relay)
        s.rect(x0 - 6, 132, 40, 34, sw=THIN, dash="1.2 0.8")
        for x in xs + [xpe]:
            s.line(x, 117.65, x, 140, LW)
        motor1(s, x0 + 3, 146, 6)
        reg(s, m, "main", x0 + 3)
        s.line(xpe, 140, xpe, 146, LW); s.line(xpe, 146, x0 + 9, 146, LW)
        s.text(x0 + 19, 141, "speed in", 1.5)
        s.text(x0 + 19, 144, "4-20 mA", 1.5)
        s.text(x0 + 19, 147, xr(f"AO{ao_ch}", "main"), 1.5)
        s.text(x0 + 19, 151, "run relay", 1.5)
        s.text(x0 + 19, 154, "-> DI " + xr(m, "fb"), 1.5)
        s.label(x0 + 14, 170, [m, f"{tag} {desc}", "230 V, ≈ 40 W", f"control {ccable}"], 1.85, anchor="middle")
    # analog output rows
    reg(s, "-A1.7", "main", 22)
    t(22, 186, "-A1.7  ANALOG OUTPUT MODULE AO4, 4-20 mA (slot 7 of -A1) · pump speed references", 2.0, bold=True)
    for i, d in enumerate(D.AO):
        y = 194 + i * 11
        p, mn, sh = d["terms"]
        s.text(20, y + 0.7, f"%QW{100 + d['ch']}", 1.8, bold=True)
        s.text(34, y + 0.7, d["tag"], 1.75)
        s.rect(54, y - 4, 14, 8, sw=0.45, fill="#fff")
        s.text(61, y + 0.6, f"AO{d['ch']}", 1.6, anchor="middle", bold=True)
        reg(s, f"AO{d['ch']}", "main", 61)
        for dy, tm, wire in ((-1.8, p, f"5{31 + 2 * i}"), (1.8, mn, f"5{32 + 2 * i}")):
            s.circle(68, y + dy, 0.7, sw=THIN, fill="#fff")
            s.line(68.7, y + dy, 129.2, y + dy, LW)
            s.text(95, y + dy - 0.5, wire, 1.45, italic=True)
            hterm(s, 130, y + dy, "X3", tm)
            s.line(130.8, y + dy, 165, y + dy, LW)
        s.line(122, y + 4.2, 140, y + 4.2, THIN, dash="0.8 0.5")
        hterm(s, 140, y + 4.2, "X3", sh)
        s.text(170, y - 0.6, f"{d['dev']}  {d['pump']} speed input 4-20 mA = 0-100 %", 1.75)
        s.text(170, y + 2.6, f"{d['cable']} {D.CABLES[d['cable']].split(',')[0]} · shield earthed in the panel only",
               1.6, color=GREY)
    notes(s, 296, 112, [
        "Dosing pumps are 230 V diaphragm pumps with their own electronics: -K311...-K313 switch the "
        "supply (enable), the speed follows the 4-20 mA reference from -A1.7.",
        "The pump's run relay closes while it is running and healthy; it is the PLC's running feedback "
        "(P311_FB...P313_FB, E-07). A pump fault or MCB trip gives A14...A16.",
        "The coils of -K311...-K313 are on 24V-S (E-08): an E-stop stops all dosing.",
        "P-313 doses 10 % nitric acid: PVDF wetted parts, drip tray, acid-resistant cable glands.",
    ], 100, 1.95)


# --- E-06 safety circuit -------------------------------------------------------
def sheet_e06(s: Sheet):
    t = s.text
    bus_in(s, 34, 24, "+24.5", xr("-F25", "main"), 320)
    reg(s, "+24.5", "load", 40)
    s.rect(30, 120, 232, 40, sw=0.45, fill="#fff")
    reg(s, "-K0", "box", 120)
    for x, lab in [(40, "A1"), (95, "S11"), (115, "S12"), (150, "S21"), (170, "S22"), (205, "S33"), (245, "S34")]:
        t(x, 124, lab, 1.8, anchor="middle")
    t(40, 158.4, "A2", 1.8, anchor="middle")
    lines = [
        ("-K0  SAFETY RELAY", 2.8, True),
        ("2-channel E-stop input with cross-fault detection · monitored manual reset at S33-S34 (acts on release)", 1.9, False),
        ("24 V DC · outputs 3 NO (13-14, 23-24, 33-34) + 1 NC (41-42) · device rated for Cat. 3 / PL d (ISO 13849-1)", 1.9, False),
        (f"Contacts:  13-14 {xr('-K0', '13-14')}   23-24 {xr('-K0', '23-24')}   33-34 {xr('-K0', '33-34')}   41-42 spare",
         1.9, False),
    ]
    yy = 132
    for txt, sz, b in lines:
        t(52, yy, txt, sz + (0.25 if not b else 0), bold=b)
        yy += 6.0
    s.dot(40, 24); s.line(40, 24, 40, 120, LW)
    s.line(40, 160, 40, 170, LW)
    zero_v(s, 40, 170, "0V", "/E-01.3")

    def channel(xo, xret, a, b, c, w1, w2, w3, t1, t2):
        """S11 -> X2:a -> -S0.1 -> X2:b -> -S0.2 -> X2:c -> S12."""
        s.line(xo, 120, xo, 104.85, LW)
        term(s, xo, 104, "X2", a, side="r")
        s.line(xo, 103.15, xo, 88, LW)
        m1 = contact(s, xo, 76, "NC", 12, t1=t2, t2=t1, func="posopen")
        s.line(xo, 76, xo, 66.85, LW)
        term(s, xo, 66, "X2", b, side="r")
        s.line(xo, 65.15, xo, 58, LW)
        m2 = contact(s, xo, 46, "NC", 12, t1=t2, t2=t1, func="posopen")
        s.line(xo, 46, xo, 40, LW); s.line(xo, 40, xret, 40, LW); s.line(xret, 40, xret, 103.15, LW)
        term(s, xret, 104, "X2", c, side="r")
        s.line(xret, 104.85, xret, 120, LW)
        wn(s, xo, 113, w1); wn(s, xo, 72, w2); wn(s, xret, 113, w3)
        return m1, m2

    a1, a2 = channel(95, 115, "1", "2", "3", "601", "602", "603", "11", "12")
    b1, b2 = channel(150, 170, "4", "5", "6", "604", "605", "606", "21", "22")
    s.line(b1[0], b1[1], 88, b1[1], THIN, dash="0.9 0.6")
    s.line(b2[0], b2[1], 88, b2[1], THIN, dash="0.9 0.6")
    E.actuator(s, a1[0], a1[1], 95, "estop")
    E.actuator(s, a2[0], a2[1], 95, "estop")
    reg(s, "-S0.1", "main", 95)
    reg(s, "-S0.2", "main", 95)
    s.label(82, 78, ["-S0.1", "E-STOP", "panel door", "-W90"], 1.9)
    s.label(82, 48, ["-S0.2", "E-STOP", "fertigation skid", "-W93, IP65 box"], 1.9)
    t(98, 37.5, "ch. 1", 1.7, color=GREY)
    t(153, 37.5, "ch. 2", 1.7, color=GREY)

    # reset with EDM (welded-contact detection on -K201 and -K541)
    xo, xret = 205, 245
    s.line(xo, 120, xo, 104.85, LW)
    term(s, xo, 104, "X2", "7", side="r")
    s.line(xo, 103.15, xo, 88, LW)
    contact(s, xo, 76, "NO", 12, act="push", t1="14", t2="13")
    s.line(xo, 76, xo, 66.85, LW)
    term(s, xo, 66, "X2", "8", side="r")
    s.line(xo, 65.15, xo, 44, LW); s.line(xo, 44, xret, 44, LW)
    wn(s, xo, 113, "607"); wn(s, xo, 55, "608")
    reg(s, "-S0R", "main", xo)
    s.label(196, 79, ["-S0R", "SAFETY RESET", "blue, NO, door"], 1.9)
    for dev, y0, wnum in (("-K201", 48, "609"), ("-K541", 66, "610")):
        s.line(xret, y0 - 4, xret, y0, LW)
        contact(s, xret, y0, "NC", 10, t1="21", t2="22", tside="l")
        reg(s, dev, "21-22", xret)
        s.label(249, y0 + 4.2, [dev, "coil " + xr(dev, "coil")], 1.9, anchor="start")
        s.line(xret, y0 + 10, xret, y0 + 14 if y0 == 48 else 120, LW)
        wn(s, xret, y0 + 13, wnum, "l")
    t(262, 104, "EDM loop: NC 21-22 of -K201 and -K541", 1.7, color=GREY)
    t(262, 107, "must be closed for a reset (welded-", 1.7, color=GREY)
    t(262, 110, "contact detection, pressure hazards)", 1.7, color=GREY)

    x = 320
    s.line(x, 24, x, 40, LW)
    contact(s, x, 40, "NO", 12, t1="13", t2="14")
    reg(s, "-K0", "13-14", x)
    s.line(x, 52, x, 64, LW); wn(s, x, 58.5, "611")
    contact(s, x, 64, "NO", 12, t1="23", t2="24")
    reg(s, "-K0", "23-24", x)
    s.label(315, 44, ["-K0", "13-14", "safety output", xr("-K0", "box")], 1.9)
    s.label(315, 68, ["-K0", "23-24", "in series", xr("-K0", "box")], 1.9)
    s.line(x, 76, x, 92, LW)
    s.line(x, 92, 396, 92, BUS)
    t(323, 90.8, "24V-S  safety-switched 24 V DC", 2.0, bold=True)
    s.dot(360, 92); s.line(360, 92, 360, 99, LW); arrow(s, 360, 100.6, "d", 1.6)
    t(361.6, 98.0, "DO supply -A1.3 1L+/2L+,", 1.75)
    t(361.6, 101.0, "-A1.4 group A", 1.6)
    t(361.6, 104.2, xr("24V-S", "do"), 1.8)
    reg(s, "24V-S", "src", 330)

    notes(s, 22, 182, [
        "Stop category 0 (IEC 60204-1 §9.2.2): -K0 removes 24V-S, so every contactor coil and solenoid valve on "
        "24V-S de-energises directly, whatever the PLC outputs are: pumps, fans and drives stop, valves close by spring.",
        "-S0.1 (door) and -S0.2 (fertigation skid) are in series in both channels; each has 2 NC contacts with "
        "positive opening (IEC 60947-5-5), latching, red mushroom on yellow ground.",
        "-S0R (blue): monitored manual reset, effective on release, only with the EDM loop closed.",
        "-K0 33-34 signals ESTOP_OK to the PLC (" + xr("-K0", "33-34") + "): monitoring only. After a reset "
        "the PLC still needs RESET (A00) and START: no automatic restart.",
    ], 196, 2.05)
    sf = [["SF", "Function", "Input", "Logic", "Final elements", "Stop", "PLr *"],
          ["SF1", "Emergency stop", "-S0.1, -S0.2 (2 NC each)", "-K0", "24V-S off: all contactors and valves",
           "cat. 0", "c"]]
    table(s, 222, 196, [10, 30, 40, 10, 58, 12, 12], sf, size=1.85, rh=5.0, title="Safety functions (hardwired)")
    s.para(222, 214, "* PLr to be confirmed by the risk assessment (ISO 12100 / ISO 13849-1). Pressure "
           "protection, dry-run protection and the vent/fan interlock are PLC functions (FDS §11), not "
           "safety functions.", 172, 1.85)


# --- I/O row sheets ------------------------------------------------------------
def module_box(s, x, y0, y1, ref, title):
    s.rect(x, y0, 14, y1 - y0, sw=0.45, fill="#fff")
    reg(s, ref, "main", x)
    s.text(x - 1.4, (y0 + y1) / 2, f"{ref}  {title}", 1.8, anchor="middle", rot=-90, bold=True)


def sheet_e07(s: Sheet):
    t = s.text
    Y = lambda ch: 30 + ch * 8.55  # noqa: E731
    XB = 205
    t(XB + 1.5, 21.4, "+24.2", 2.0, bold=True)
    t(XB + 11, 21.4, "from " + xr("-F22", "main"), 1.6, color=GREY)
    reg(s, "+24.2", "load", XB)
    s.line(XB, 23, XB, Y(len(D.DI) - 1), BUS)
    t(17, 21.4, "Address", 1.7, color=GREY); t(31, 21.4, "Tag", 1.7, color=GREY)
    t(XB + 6, 25.5, "Signal", 1.7, color=GREY); t(316, 25.5, "Contact · 1 =", 1.7, color=GREY)
    module_box(s, 54, Y(0) - 4.3, Y(15) + 4.3, "-A1.1", "DI16 24 V DC sinking")
    module_box(s, 54, Y(16) - 4.3, Y(24) + 4.3, "-A1.2", "DI16 (ch. 9...15 spare)")
    for d in D.DI:
        ch, y = d["ch"], Y(d["ch"])
        t(17, y + 0.6, f"%IX{100 + ch // 8}.{ch % 8}", 1.75, bold=True)
        t(31, y + 0.6, d["tag"], 1.7)
        t(61, y + 0.6, f"DI{ch % 16}", 1.55, anchor="middle", bold=True)
        s.circle(68, y, 0.7, sw=THIN, fill="#fff")
        t(XB + 6, y + 0.6, d["desc"], 1.75)
        t(316, y + 0.6, f"{d.get('sense', 'NO')} · {d['one']}", 1.7)
        wire = DI_WIRE[ch]
        t(88, y - 0.6, wire, 1.45, italic=True)
        if d["kind"] == "int1":
            dev = d["devs"][0]
            s.line(68.7, y, 150, y, LW)
            hcontact(s, 150, y, d["sense"])
            reg(s, dev, d["pins"][0], 150)
            t(140, y - 1.9, f"{dev} {d['pins'][0]}  " + xr(dev, "box" if dev == "-K0" else "main"), 1.45)
            s.line(160, y, XB, y, LW)
        elif d["kind"] == "int2":
            q, k = d["devs"]
            s.line(68.7, y, 130, y, LW)
            hcontact(s, 130, y, "NO"); reg(s, q, "13-14", 130)
            s.line(140, y, 155, y, LW)
            hcontact(s, 155, y, "NO"); reg(s, k, "13-14", 155)
            t(122, y - 1.9, f"{q} 13-14 {xr(q, 'main')}", 1.45)
            t(150, y - 1.9, f"{k} 13-14 coil {xr(k, 'coil')}", 1.45)
            s.line(165, y, XB, y, LW)
        else:
            a, b = d["terms"]
            dev = d["devs"][0]
            s.line(68.7, y, 119.2, y, LW)
            hterm(s, 120, y, "X2", b)
            s.line(120.8, y, 150, y, LW)
            hcontact(s, 150, y, d["sense"], act=d.get("act"))
            reg(s, dev, "fb" if dev.startswith("-M3") else "main", 150)
            t(127, y - 1.9, f"{dev} {d['dtext']} · {d['cable']}", 1.45)
            s.line(160, y, 184.2, y, LW)
            hterm(s, 185, y, "X2", a)
            s.line(185.8, y, XB, y, LW)
        s.dot(XB, y)
    y_end = Y(len(D.DI) - 1) + 8
    t(17, y_end + 2, "Field contacts switch +24.2 (-F22) to the input; the input sinks to 0V inside the module "
                     "(module 0V terminal M to the 0V bus, /E-01). Discrete inputs 0...24 -> OpenPLC remote "
                     "device PLANT -> %IX100.0...%IX103.0.", 1.75)
    t(17, y_end + 5.2, "Fail-safe wiring: ESTOP_OK, PB_STOP_OK, the LSL low-level switches, RAIN_DRY and the motor-"
                       "healthy contacts are closed when healthy, so a broken wire or loss of the remote I/O "
                       "reads as the safe state (FDS §4.1).", 1.75)


def sheet_e08(s: Sheet):
    t = s.text
    Y = lambda ch: 30 + ch * 9.3  # noqa: E731
    XB = 205
    t(XB + 1.5, 21.4, "0V", 2.0, bold=True)
    t(XB + 6, 21.4, "/E-01", 1.6, color=GREY)
    s.line(XB, 23, XB, Y(len(D.DO) - 1), BUS)
    t(17, 21.4, "Address", 1.7, color=GREY); t(31, 21.4, "Tag", 1.7, color=GREY)
    t(XB + 6, 25.5, "Load", 1.7, color=GREY); t(300, 25.5, "Contacts of the coil (mirror)", 1.7, color=GREY)
    module_box(s, 54, Y(0) - 4.6, Y(15) + 4.6, "-A1.3", "DO16 24 V DC 0.5 A")
    module_box(s, 54, Y(16) - 4.6, Y(21) + 4.6, "-A1.4", "DO8 (ch. 6, 7 spare)")
    reg(s, "24V-S", "do", 54)
    reg(s, "+24.3", "load", 54)
    t(17, Y(len(D.DO) - 1) + 9, "Supply: -A1.3 groups 1L+ (ch. 0...7) and 2L+ (ch. 8...15) and -A1.4 group A "
                                "(ch. 0...3) from 24V-S " + xr("24V-S", "src") + "; -A1.4 group B (ch. 4...7) "
                                "from +24.3 " + xr("-F23", "main") + ", so amber and red stay lit on an E-stop.",
      1.75)
    t(17, Y(len(D.DO) - 1) + 12.2, "Outputs are high-side, short-circuit proof, 0.5 A. Solenoids with DIN 43650 "
                                   "plugs including suppressor diodes; contactor coils with plug-in suppressor "
                                   "modules.", 1.75)
    for d in D.DO:
        ch, y = d["ch"], Y(d["ch"])
        t(17, y + 0.6, f"%QX{100 + ch // 8}.{ch % 8}", 1.75, bold=True)
        t(31, y + 0.6, d["tag"], 1.7)
        t(61, y + 0.6, f"DO{ch % 16}", 1.55, anchor="middle", bold=True)
        s.circle(68, y, 0.7, sw=THIN, fill="#fff")
        t(XB + 6, y + 0.6, d["desc"], 1.75)
        wire = DO_WIRE[ch]
        t(80, y - 0.6, wire, 1.45, italic=True)
        load, dev = d["load"], d["dev"]
        if load == "sol":
            a, b = d["terms"]
            s.line(68.7, y, 119.2, y, LW)
            hterm(s, 120, y, "X2", a)
            s.line(120.8, y, 150, y, LW)
            hcoil(s, 150, y)
            reg(s, dev, "main", 150)
            t(140, y - 2.7, f"{dev} solenoid 24 V DC · {d['cable']}", 1.45)
            s.line(158, y, 184.2, y, LW)
            hterm(s, 185, y, "X2", b)
            s.line(185.8, y, XB, y, LW)
            t(300, y + 0.6, "spring return: closed when de-energised", 1.6, color=GREY)
        elif load == "coil":
            s.line(68.7, y, 150, y, LW)
            hcoil(s, 150, y)
            reg(s, dev, "coil", 150)
            t(140, y - 2.7, f"{dev} contactor coil", 1.45)
            s.line(158, y, XB, y, LW)
            cells = [f"{t1}-{t2} " + (xr(dev, f"{t1}-{t2}") if (dev, f"{t1}-{t2}") in E.REG else
                                      ("spare" if E.PASS == 2 else "/?")) for t1, t2, _k in D.contacts_of(dev)]
            t(300, y + 0.6, "  ".join(cells), 1.55)
        elif load == "coil_sw":
            a, b = d["terms"]
            s.line(68.7, y, 99.2, y, LW)
            hterm(s, 100, y, "X2", a)
            s.line(100.8, y, 110, y, LW)
            kind = d.get("swkind", "NC")
            hcontact(s, 110, y, kind, act="limit" if kind == "NC" else "pressure")
            reg(s, "lim", d["sw"], 110)
            reg(s, d["sw"], "nc", 110)
            t(101, y - 2.7, f"{d['sw']} {d['swtext']}", 1.45)
            s.line(120, y, 129.2, y, LW)
            hterm(s, 130, y, "X2", b)
            t(136, y - 0.6, f"8{ch + 31:02d}", 1.45, italic=True)
            if d["ilk"]:
                s.line(130.8, y, 136, y, LW)
                hcontact(s, 136, y, "NC")
                reg(s, d["ilk"], "21-22", 136)
                t(136, y + 3.6, f"{d['ilk']} 21-22", 1.4)
                s.line(146, y, 150, y, LW)
            else:
                s.line(130.8, y, 150, y, LW)
            hcoil(s, 150, y)
            reg(s, dev, "coil", 150)
            t(152, y - 2.7, f"{dev} coil", 1.45)
            s.line(158, y, XB, y, LW)
            cells = [f"{t1}-{t2} " + (xr(dev, f"{t1}-{t2}") if (dev, f"{t1}-{t2}") in E.REG else
                                      ("spare" if E.PASS == 2 else "/?")) for t1, t2, _k in D.contacts_of(dev)]
            t(300, y + 0.6, "  ".join(cells), 1.55)
        elif load == "lamp":
            tm = LAMP_TERMS[ch]
            s.line(68.7, y, 119.2, y, LW)
            hterm(s, 120, y, "X2", tm)
            s.line(120.8, y, 151.5, y, LW)
            lamp(s, 154, y, 2.4)
            reg(s, dev, "main", 154)
            t(141, y - 3.0, f"{dev} {d['colour']} · -W91", 1.45)
            s.line(156.4, y, 180, y, LW)
            if ch == 21:
                hterm(s, 185, y, "X2", LAMP_COMMON)
                s.line(180, y, 184.2, y, LW)
                s.line(185.8, y, XB, y, LW)
                s.line(180, Y(19), 180, y, LW)
                s.dot(180, Y(20)); s.dot(180, y)
        if load != "lamp" or ch == 21:
            s.dot(XB, y)


def sheet_e09(s: Sheet):
    t = s.text
    Y = lambda ch: 33 + ch * 13.2  # noqa: E731
    t(17, 21.4, "Address", 1.7, color=GREY); t(31, 21.4, "Tag", 1.7, color=GREY)
    t(232, 25.5, "Range (4-20 mA)", 1.7, color=GREY); t(300, 25.5, "On signal fault (< 3.6 mA)", 1.7, color=GREY)
    module_box(s, 54, Y(0) - 6, Y(7) + 6, "-A1.5", "AI8 4-20 mA")
    module_box(s, 54, Y(8) - 6, Y(14) + 6, "-A1.6", "AI8 (ch. 7 spare)")
    reg(s, "+24.4", "load", 54)
    fallback = {"A20": "refill blocked", "A21": "irrigation trips", "A22": "irrigation trips",
                "A23": "irrigation trips", "A24": "use AIT-303", "A25": "use AIT-302", "A27": "drain % frozen",
                "A29": "radiation sum frozen", "A31": "display only", "A30": "storm assumed",
                "A32": "vent 50 %, COOL/fog blocked", "A33": "humidity venting, fog off", "A34": "display only",
                "A35": "vent on limit switches"}
    for d in D.AI:
        ch, y = d["ch"], Y(d["ch"])
        p, m, sh = d["terms"]
        w1, w2 = AI_WIRE[ch]
        t(17, y + 0.6, f"%IW{100 + ch}", 1.75, bold=True)
        t(31, y + 0.6, d["tag"], 1.7)
        t(61, y + 0.6, f"AI{ch % 8}", 1.55, anchor="middle", bold=True)
        two = d["wiring"] == "2w"
        labs = (("+24V", w1, p), ("AI", w2, m)) if two else (("AI", w1, p), ("M", w2, m))
        for dy, (lab, wire, tm) in zip((-2.0, 2.0), labs):
            s.circle(68, y + dy, 0.7, sw=THIN, fill="#fff")
            t(66.6, y + dy + 0.55, lab, 1.3, anchor="end")
            s.line(68.7, y + dy, 119.2, y + dy, LW)
            t(88, y + dy - 0.5, wire, 1.45, italic=True)
            hterm(s, 120, y + dy, "X3", tm)
            s.line(120.8, y + dy, 160, y + dy, LW)
        s.line(112, y + 5.0, 135, y + 5.0, THIN, dash="0.8 0.5")
        hterm(s, 135, y + 5.0, "X3", sh)
        s.ellipse(145, y, 3.2, 4.4, dash="0.8 0.5")
        s.rect(160, y - 4.4, 64, 8.8, sw=LW, fill="#fff")
        reg(s, d["dev"], "main", 160)
        reg(s, d["isa"], "main", 160)
        t(161.5, y - 1.3, f"{d['dev']}  {d['isa']}  {d['desc']}", 1.6, bold=True)
        t(161.5, y + 1.6, d["what"] + ("" if two else ""), 1.45)
        t(161.5, y + 3.7, ("2-wire, loop-powered by the module" if two else
                           ("active output, own supply " + ("230 V (-F4)" if "230" in d["what"] else "+24.4"))) +
          f" · {d['cable']}", 1.4, color=GREY)
        lo, hi, unit = d["rng"]
        t(232, y + 0.6, f"{lo}-{hi} {unit}", 1.75)
        t(300, y + 0.6, f"{d['alarm']} after 1 s · {fallback[d['alarm']]}", 1.7)
    y_end = Y(14) + 10
    t(17, y_end, "%IW115 CLOCK_MIN is not wired: it is the coupler's NTP-synchronised clock register (minutes since "
                 "midnight), read in the same input-register block (FDS §5.3).", 1.75)
    t(17, y_end + 3.2, "Raw value = mA × 65535 / 20; 4 mA = 13107. Below 3.6 mA (raw ≤ 11796) the PLC flags a signal "
                       "fault (NAMUR NE 43). Shields are earthed at the panel end only (shield clamps at -X3).", 1.75)


# --- E-10 / E-11 terminal plans ------------------------------------------------
TERM_W = [9, 9, 27, 21, 11, 54, 12]
TERM_HEAD = ["Term.", "Wire", "Panel side", "Field side", "Cable", "Function / signal", "Sheet"]


def strip_rows(name, lo=None, hi=None):
    rows = [TERM_HEAD]
    for tm in TERMINALS:
        if tm[0] == name and (lo is None or lo <= int(tm[1]) <= hi):
            rows.append([tm[1], tm[2], tm[3], tm[4], tm[5], tm[6], xr(tm[0], tm[1])])
    return rows


def sheet_e10(s: Sheet):
    rows = strip_rows("X2")
    reg(s, "-X2", "main", 18)
    half = 1 + (len(rows) - 1 + 1) // 2
    table(s, 18, 25, TERM_W, rows[:half], size=1.65, rh=3.95,
          title="-X2  24 V DC digital I/O and safety (2.5 mm², spring clamp)")
    table(s, 210, 25, TERM_W, [TERM_HEAD] + rows[half:], size=1.65, rh=3.95)
    notes(s, 210, 25 + (len(rows) - half + 1) * 3.95 + 10, [
        "Numbering by function: -X2:1-8 safety circuit (E-06), 11-42 digital inputs in channel order (E-07), "
        "101-122 outputs to field devices on 24V-S, 131-134 stack light (E-08). Gaps are reserve.",
        "Supply terminals of the inputs are bridged from +24.2 (-F22); 0 V returns are bridged to 0V.",
        "Panel side = internal wiring, field side = cable core. Wire numbers per E-00.",
    ], 186, 1.9)


def sheet_e11(s: Sheet):
    for strip in ("-X1", "-X3", "-X4"):
        reg(s, strip, "main", 18)
    y = table(s, 18, 25, TERM_W, strip_rows("X3"), size=1.6, rh=3.7,
              title="-X3  analog (2.5 mm², shield clamps)")
    _ = y
    x2 = 166
    widths = [8, 9, 23, 17, 9, 38, 11]
    rows4 = [TERM_HEAD] + [[tm[1], tm[2], tm[3], tm[4], tm[5], tm[6], xr(tm[0], tm[1])]
                           for tm in TERMINALS if tm[0] == "X4"]
    yb = table(s, 18 + 145 + 5, 25, widths, rows4, size=1.55, rh=3.7, title="-X4  outgoing power (4 mm²)")
    rows1 = [TERM_HEAD] + [[tm[1], tm[2], tm[3], tm[4], tm[5], tm[6], xr(tm[0], tm[1])]
                           for tm in TERMINALS if tm[0] == "X1"]
    table(s, 18 + 145 + 5, yb + 8, widths, rows1, size=1.55, rh=3.7, title="-X1  230/400 V AC")
    cab = [["Cable", "Type"]] + [[k, v] for k, v in D.CABLES.items()]
    table(s, x2 + 118 + 4, 25, [14, 103 - 14 - 1], cab, size=1.45, rh=3.25, title="Cables")


# --- E-12 panel layout -----------------------------------------------------------
RAILS = [
    ("rail 1 - main and power", ["-Q0", "-F1", "-F2", "-F3", "-F4", "-G1", "-F21", "-F22", "-F23", "-F24", "-F25",
                                 "-K0"]),
    ("rail 2 - pump feeders", ["-Q201", "-K201", "-Q531", "-K531", "-Q541", "-K541", "-F311", "-K311", "-F312",
                               "-K312", "-F313", "-K313"]),
    ("rail 3 - climate feeders", ["-Q601", "-K601", "-Q602", "-K602", "-Q603", "-K603", "-Q511", "-K511.1",
                                  "-K511.2", "-Q521", "-K521.1", "-K521.2"]),
    ("rail 4 - control", ["-A10", "-A11", "-A1", "-A1.1", "-A1.2", "-A1.3", "-A1.4", "-A1.5", "-A1.6", "-A1.7"]),
    ("rail 5 - terminals", ["-X1", "-X4", "-X2", "-X3", "-X0"]),
]
WIDTH_MM = {"-Q0": 72, "-F1": 36, "-F2": 36, "-F3": 72, "-F4": 36, "-G1": 65, "-F21": 18, "-F22": 18, "-F23": 18,
            "-F24": 18, "-F25": 18, "-K0": 45, "-A10": 110, "-A11": 60, "-A1": 50, "-X1": 70, "-X4": 200,
            "-X2": 330, "-X3": 160, "-X0": 60}


def sheet_e12(s: Sheet):
    t = s.text
    k = 1 / 6
    X0, Y0, PW, PH = 24.0, 30.0, 1000.0, 1200.0
    t(X0, 21, "MOUNTING PLATE (front view, door removed)", 2.6, bold=True)
    t(X0, 24.8, "enclosure 1000 W x 1200 H x 300 D mm, IP55, steel, wall-mounted in the pump room", 1.9)
    s.rect(X0, Y0, PW * k, PH * k, sw=0.5, rx=1.2)
    rail_y = [70, 280, 490, 700, 960]
    for (title, devs), ry in zip(RAILS, rail_y):
        y = Y0 + ry * k
        s.rect(X0 + 30 * k, y - 8 * k, (PW - 60) * k, 16 * k, sw=THIN, fill="#ddd")
        t(X0 + (PW - 34) * k, y - 3.0, title, 1.6, anchor="end", color=GREY)
        x = X0 + 40 * k
        for dev in devs:
            w = WIDTH_MM.get(dev, 45 if dev.startswith(("-Q", "-K")) else 36)
            h = 120 if dev.startswith(("-A1", "-A10", "-G")) else 90 if not dev.startswith("-X") else 60
            if x + w * k > X0 + (PW - 40) * k:
                break
            s.rect(x, y - h * k / 2, w * k, h * k, sw=LW, fill="#fff")
            reg(s, dev, "layout", x)
            s.text(x + w * k / 2, y + 0.6, dev, 1.35 if w > 25 else 1.15, anchor="middle", rot=0 if w > 25 else -90)
            x += w * k + 2 * k
        if ry < 960:
            s.rect(X0 + 30 * k, y + 70 * k, (PW - 60) * k, 60 * k, sw=THIN, dash="1 0.8")
            t(X0 + PW * k / 2, y + 102 * k, "cable duct 60 x 60", 1.3, anchor="middle", color=GREY)
    s.rect(X0 + 30 * k, Y0 + 1100 * k, (PW - 60) * k, 60 * k, sw=THIN, fill="#eee")
    t(X0 + PW * k / 2, Y0 + 1135 * k, "gland plate: cables enter from below (EMC glands for shielded cables)",
      1.5, anchor="middle")
    # door
    DX0 = 220.0
    t(DX0, 21, "DOOR (front view)", 2.6, bold=True)
    s.rect(DX0, Y0, PW * k, PH * k, sw=0.5, rx=1.2)
    items = [("-Q0", 500, 150, 70, "main switch"), ("-S0.1", 500, 380, 40, "E-STOP"),
             ("-S0R", 380, 380, 22, "reset"), ("-S1", 300, 560, 22, "START"), ("-S2", 500, 560, 22, "STOP"),
             ("-S3", 700, 560, 22, "RESET"), ("-E1", 200, 1000, 120, "filter fan"),
             ("-E1", 800, 1000, 120, "outlet filter")]
    for dev, cx, cy, size, lab in items:
        x, y = DX0 + cx * k, Y0 + cy * k
        if dev.startswith("-S"):
            s.circle(x, y, size * k / 2 + 1.2, sw=LW, fill="#fff" if dev != "-S0.1" else "#ffd400")
            if dev == "-S0.1":
                s.circle(x, y, size * k / 2, sw=LW, fill="#d22")
        else:
            s.rect(x - size * k / 2, y - size * k / 2, size * k, size * k, sw=LW, fill="#fff")
        reg(s, dev, "door", x)
        t(x, y + size * k / 2 + 3.6, f"{dev} {lab}", 1.5, anchor="middle")
    t(DX0 + 500 * k, Y0 - 1.5, "-P1 stack light on the roof", 1.6, anchor="middle")
    reg(s, "-P1", "main", DX0 + 500 * k)
    s.para(DX0, Y0 + PH * k + 5, "Heat load ≈ 120 W (power supply, coupler, PLC, contactors). Filter fan -E1 "
           "switched by -B1 at 35 °C keeps the panel below 45 °C at 38 °C ambient. Spare space ≥ 20 % on every rail.",
           170, 1.8)


# --- E-13 parts list ---------------------------------------------------------------
def sheet_e13(s: Sheet):
    def where(ref):
        for key in ("main", "coil", "box", "fb", "nc", "door", "layout"):
            if (ref, key) in E.REG:
                return xr(ref, key)
        return "-"
    rows = [[ref, desc, loc, where(ref)] for ref, desc, loc in D.DEVICES]
    n = (len(rows) + 2) // 3
    head = ["Ref.", "Description", "Loc.", "Sheet"]
    widths = [15, 86, 12, 13]
    for i in range(3):
        part = rows[i * n:(i + 1) * n]
        table(s, 18 + i * 130, 25, widths, [head] + part, size=1.45, rh=5.0,
              title="Parts list" if i == 0 else None)


# --- E-14 network ------------------------------------------------------------------
def sheet_e14(s: Sheet):
    t = s.text

    def node(x, y, w, h, ref, lines, key="main"):
        boxed(s, x, y, w, h, [ref] + lines, size=2.0)
        reg(s, ref, key, x)

    node(150, 40, 100, 28, "-A11", ["Ethernet switch, managed, 8 ports", "VLAN 10 control · 24 V DC (+24.1)"])
    node(30, 100, 110, 34, "-A10", ["PLC: industrial PC, Linux + Docker", "OpenPLC Runtime v4.3 (50 ms task)",
                                    "192.168.10.10 · Modbus TCP server :502", "HTTPS API :8443 (Editor upload)"])
    node(160, 100, 100, 34, "-A1", ["Remote I/O coupler, Modbus TCP slave", "192.168.10.20 :502 · unit 1",
                                    "NTP clock -> IR 15 (CLOCK_MIN)", "1 s output watchdog"], key="net")
    node(285, 100, 105, 34, "-A13", ["Router / firewall (office)", "192.168.10.1 · NTP server",
                                     "VPN for remote support only", "no port forwarding to :502"])
    node(285, 160, 105, 30, "-A12", ["HMI PC (office), web browser", "farmsim hmi on 192.168.10.30 :8080",
                                     "Modbus TCP client of -A10"])
    for x1, y1, cable in ((85, 100, "-W501"), (210, 100, "-W502"), (337, 100, "-W503")):
        s.line(x1, y1, x1, 75, LW); s.line(x1, 75, 200, 75, LW) if x1 < 200 else s.line(200, 75, x1, 75, LW)
        t(x1 + 1.5, 86, cable, 1.8)
    s.line(200, 68, 200, 75, LW)
    s.line(337, 134, 337, 160, LW); t(339, 148, "office LAN", 1.8)
    mods = [("-A1.1", "DI16", "%IX100.0-101.7"), ("-A1.2", "DI16", "%IX102.0-103.0"), ("-A1.3", "DO16", "%QX100.0-101.7"),
            ("-A1.4", "DO8", "%QX102.0-102.5"), ("-A1.5", "AI8", "%IW100-107"), ("-A1.6", "AI8", "%IW108-114"),
            ("-A1.7", "AO4", "%QW100-102")]
    for i, (ref, kind, addr) in enumerate(mods):
        x = 30 + i * 32
        boxed(s, x, 160, 30, 16, [ref, kind, addr], size=1.7)
        s.line(x + 15, 160, x + 15, 152, THIN)
    s.line(45, 152, 237, 152, THIN); s.line(210, 134, 210, 152, THIN)
    t(30, 184, "I/O modules on the coupler backplane (slots 1-7) · OpenPLC remote device PLANT: DI fc 2 (32), "
               "IR fc 4 (16), coils fc 15 (24), HR fc 16 (3), cycle 50 ms, read groups 'set to zero' on comms loss.", 1.8)
    rows = [["Node", "Address", "Port / protocol", "Talks to"],
            ["-A10 PLC", "192.168.10.10", "502 Modbus TCP server, 8443 HTTPS", "-A1 (master), -A12 (server)"],
            ["-A1 coupler", "192.168.10.20", "502 Modbus TCP slave", "-A10 only (allow-list)"],
            ["-A12 HMI", "192.168.10.30", "8080 HTTP (local), Modbus client", "-A10"],
            ["-A13 router", "192.168.10.1", "NTP 123, VPN", "-A1 time, remote support"]]
    table(s, 30, 200, [30, 30, 62, 58], rows, size=1.9, rh=4.8, title="Addresses")
    notes(s, 220, 200, [
        "Modbus TCP has no authentication: the control VLAN is isolated, the router allows no inbound "
        "traffic to :502 and remote access goes through the VPN only (IEC 62443 zone 'control').",
        "Loss of the coupler link: OpenPLC zeroes the PLANT inputs, the program trips with A00; the coupler's "
        "own watchdog drops its outputs after 1 s (FDS §13).",
    ], 170, 1.9)


SHEET_FUNCS = {"E-00": sheet_e00, "E-01": sheet_e01, "E-02": sheet_e02, "E-03": sheet_e03, "E-04": sheet_e04,
               "E-05": sheet_e05, "E-06": sheet_e06, "E-07": sheet_e07, "E-08": sheet_e08, "E-09": sheet_e09,
               "E-10": sheet_e10, "E-11": sheet_e11, "E-12": sheet_e12, "E-13": sheet_e13, "E-14": sheet_e14}


def build_all() -> list[Sheet]:
    out = []
    for i, (code, title) in enumerate(D.SHEETS):
        s = Sheet(code, title, i)
        SHEET_FUNCS[code](s)
        frame(s)
        out.append(s)
    return out


# =============================================================================
# OUTPUT FILES
# =============================================================================
def write_index(sheets) -> None:
    parts = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
             f"<title>{E.esc(D.PROJECT)} - electrical drawings rev. {D.REV}</title>", "<style>",
             "@page { size: A3 landscape; margin: 0 }", "html, body { margin: 0; padding: 0; background: #fff }",
             ".sheet { width: 420mm; height: 297mm; overflow: hidden; break-after: page; page-break-after: always }",
             ".sheet:last-child { break-after: auto; page-break-after: auto }",
             ".sheet svg { display: block; width: 420mm; height: 297mm }",
             "@media screen { body { background: #777 } .sheet { margin: 8mm auto; box-shadow: 0 0 6px #0008 } }",
             "</style></head><body>"]
    for s in sheets:
        parts += [f'<div class="sheet" id="{s.code}">', s.svg(), "</div>"]
    parts.append("</body></html>")
    (OUT_DIR / "index.html").write_text("\n".join(parts), encoding="utf-8", newline="\n")


def write_readme() -> None:
    lines = [f"# {D.PROJECT} - electrical drawings", "",
             f"Revision {D.REV}, {D.DATE}. A3 landscape, IEC 60617 symbols, IEC 81346 reference designations.", "",
             "| Sheet | Drawing no. | Title |", "|---|---|---|"]
    for i, (code, title) in enumerate(D.SHEETS):
        lines.append(f"| {i + 1} / {len(D.SHEETS)} | [{D.DOC_PREFIX}{code}]({D.DOC_PREFIX}{code}.svg) | {title} |")
    lines += ["", "All sheets in one file: [index.html](index.html) (print-ready) and "
              "[GH1-electrical.pdf](GH1-electrical.pdf). The I/O loop-check sheet is "
              "[../IO_CHECKOUT.md](../IO_CHECKOUT.md).", "", "## Regenerate", "", "```",
              "python tools/drawings/make_drawings.py", "```", "",
              "Standard library only. Devices, feeders, I/O channels and cables are defined once in "
              "`tools/drawings/gh1_data.py`. The schematics, the terminal plans (E-10, E-11), the parts list "
              "(E-13) and `docs/IO_CHECKOUT.md` are all generated from it, with terminal numbers assigned "
              "automatically and cross-references resolved in two passes. The script also checks the I/O "
              "against `farmsim/tags.py`. The drawing engine (`engine.py`) comes from the T-101 project. "
              "To make the PDF, print `index.html` with headless Chrome or Edge:", "", "```",
              "chrome --headless=new --disable-gpu --no-pdf-header-footer "
              "--print-to-pdf=<abs path>/GH1-electrical.pdf file:///<abs path>/index.html", "```", "",
              "## Conventions", "",
              "- **Reference designations**: product aspect with prefix `-`, letter codes per IEC 81346-2. Feeders "
              "and field devices take the P&ID loop number: `-K201`/`-M201` = P-201, `-Y401` = XV-401, "
              "`-B202` = LSL-201.",
              "- **Cross-references**: `/E-08.4` = drawing GH1-E-08, column 4. The output sheet lists for every "
              "contactor coil where its contacts are drawn; each contact names its coil's location.",
              "- **Wire numbers**: potentials keep their name (`L1 L2 L3 N PE`, `+24.1`...`+24.5`, `24V-S`, `0V`). "
              "Other wires are `<sheet><nn>` (e.g. `705` is drawn on E-07).",
              "- **Terminals**: `-X1` 230/400 V AC, `-X2` 24 V DC digital and safety (1-8 safety, 11-42 inputs, "
              "101-134 outputs), `-X3` analog (3 per loop: +, -, shield), `-X4` outgoing power, `-X0` PE bar.",
              "- **Safety**: both E-stops act through the safety relay `-K0`, which switches the actuator rail "
              "`24V-S`. The PLC only monitors it (`ESTOP_OK`)."]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_checkout() -> None:
    L = []
    a = L.append

    def row(cols):
        a("| " + " | ".join(str(c) for c in cols) + " |")

    a(f"# I/O checkout and loop check - {D.PROJECT}")
    a("")
    a(f"| Document | IOC-GH1, rev. {D.REV}, {D.DATE} |")
    a("|---|---|")
    a("| Based on | [FDS](FDS.md) §4 (I/O list), §11 (interlocks); drawings [GH1-E-06...E-11](drawings/README.md) |")
    a("| Site / panel | GH-1 control panel, pump room |")
    a("| Tested by / date | |")
    a("| Witnessed by / date | |")
    a("")
    a("Generated by `tools/drawings/make_drawings.py` from the same data as the drawings, so terminal and wire "
      "numbers match the terminal plans E-10 and E-11. Fill in by hand or print.")
    a("")
    a("## Instruments")
    a("")
    row(["Instrument", "Use", "Serial / cal. due"]); row(["---"] * 3)
    for ins in (("Digital multimeter, CAT III 600 V", "voltages, continuity, mA in series"),
                ("Loop calibrator (mA source / 2-wire simulate / measure, ±0.02 %)", "AI and AO loops"),
                ("Insulation resistance tester 500 V DC", "IEC 60204-1 §18.3 before energising"),
                ("Low-ohm continuity tester (≥ 0.2 A)", "PE continuity, IEC 60204-1 §18.2"),
                ("Phase rotation meter", "-X1 incoming supply, motor direction"),
                ("Hand-held EC and pH meters, reference thermo-hygrometer", "analyser and climate sensor checks"),
                ("Laptop with the web HMI and OpenPLC Editor", "manual mode, live values, debugger")):
        row(list(ins) + [""])
    a("")
    a("## Preconditions")
    a("")
    for p in ("Panel built and inspected against drawings GH1-E-01...E-12; all wire ferrules and terminal markers fitted.",
              "Dead tests recorded: PE continuity (-X0 to every exposed conductive part), insulation resistance of the "
              "power circuits ≥ 1 MΩ at 500 V DC with electronics disconnected and the 0V-PE link at -X0 opened.",
              "Supply checked at -X1: 400 V between phases, 230 V L-N, phase rotation clockwise.",
              "Power-up in steps: -Q0 ON, -F1 ON, 24.0 V DC (±1 %) at -G1; then -F21...-F25 one at a time.",
              "OpenPLC Runtime v4 running `plc/greenhouse.st`; remote device PLANT pointing at -A1 192.168.10.20:502 "
              "(docs/openplc.md). HMI connected (E-14).",
              "Mechanical systems ready before any motor runs: pumps primed, fans guarded, vent and net drives free, "
              "acid circuit filled with water for the first runs."):
        a(f"- [ ] {p}")
    a("")
    a("Outputs are tested from the HMI in **IRR MANUAL** or **CLIM MANUAL**, so the PLC interlocks stay active "
      "(FDS §5.1). Only the stack light has no manual command: use the OpenPLC Editor debugger to force it, with "
      "nothing else forced. Remove every force at the end.")
    a("")
    hdr = ["#", "Tag", "PLC address", "Module / ch.", "Terminals (wire)", "Field device", "Test method",
           "Expected result", "Pass", "Initials", "Date"]
    a("## 1. Digital inputs (-A1.1 / -A1.2, sheet E-07)")
    a("")
    row(hdr); row(["---"] * len(hdr))
    for d in D.DI:
        ch, tag = d["ch"], d["tag"]
        addr = f"%IX{100 + ch // 8}.{ch % 8}"
        mod = f"-A1.{1 if ch < 16 else 2} / DI{ch % 16}"
        if d["kind"] == "field":
            terms = f"-X2:{d['terms'][0]} / -X2:{d['terms'][1]} ({DI_WIRE[ch]})"
        else:
            terms = f"internal ({DI_WIRE[ch]})"
        dev = " + ".join(d["devs"])
        test, exp = di_test(d, addr)
        row([f"DI{ch}", f"`{tag}`", f"`{addr}`", mod, terms, f"{dev} {d.get('dtext', d['desc'])}", test, exp, "☐", "", ""])
    a("")
    a("## 2. Digital outputs (-A1.3 / -A1.4, sheet E-08)")
    a("")
    a("Outputs on 24V-S need the E-stops released and -K0 reset. Watch the module LED, then the field device.")
    a("")
    row(hdr); row(["---"] * len(hdr))
    for d in D.DO:
        ch, tag = d["ch"], d["tag"]
        addr = f"%QX{100 + ch // 8}.{ch % 8}"
        mod = f"-A1.{3 if ch < 16 else 4} / DO{ch % 16}"
        if d["load"] in ("sol", "coil_sw"):
            terms = f"-X2:{d['terms'][0]} / -X2:{d['terms'][1]} ({DO_WIRE[ch]})"
        elif d["load"] == "lamp":
            terms = f"-X2:{LAMP_TERMS[ch]} / -X2:{LAMP_COMMON} ({DO_WIRE[ch]})"
        else:
            terms = f"internal ({DO_WIRE[ch]})"
        test, exp = do_test(d, addr)
        row([f"DO{ch}", f"`{tag}`", f"`{addr}`", mod, terms, f"{d['dev']} {d['desc']}", test, exp, "☐", "", ""])
    a("")
    a("## 3. Analog inputs (-A1.5 / -A1.6, sheet E-09)")
    a("")
    a("Raw value = mA × 65535 / 20 (FDS §4.2). Tolerance ±0.25 % of span unless the module data sheet states better. "
      "2-wire loops: calibrator in *simulate* mode in place of the transmitter. Active (4-wire) loops: calibrator "
      "in *source* mode in place of the transmitter output.")
    a("")
    row(hdr); row(["---"] * len(hdr))
    for d in D.AI:
        p, m, _sh = d["terms"]
        lo, hi, unit = d["rng"]
        mid = (lo + hi) / 2
        mode = "simulate (2-wire)" if d["wiring"] == "2w" else "source (active loop)"
        test = (f"Lift the field cores at -X3:{p} / -X3:{m}; calibrator in {mode}. Set 4 / 12 / 20 mA, then 3.0 mA. "
                f"Reconnect and compare the reading with a reference measurement at {d['isa']}.")
        exp = (f"{lo:g} / {mid:g} / {hi:g} {unit} on the HMI (raw 13107 / 39321 / 65535); 3.0 mA: {d['alarm']} after "
               f"1 s and its fallback (E-09).")
        row([f"AI{d['ch']}", f"`{d['tag']}`", f"`%IW{100 + d['ch']}`", f"-A1.{5 if d['ch'] < 8 else 6} / AI{d['ch'] % 8}",
             f"-X3:{p} / -X3:{m} ({AI_WIRE[d['ch']][0]}/{AI_WIRE[d['ch']][1]})", f"{d['dev']} {d['isa']}",
             test, exp, "☐", "", ""])
    a("")
    a("## 4. Analog outputs (-A1.7, sheet E-05)")
    a("")
    row(hdr); row(["---"] * len(hdr))
    for i, d in enumerate(D.AO):
        p, m, _sh = d["terms"]
        test = (f"IRR MANUAL, {d['pump']} supply off (-F31{i + 1} OFF). Set manual dosing 0 / 50 / 100 %; measure "
                f"the current in series at -X3:{p}. Then -F31{i + 1} ON with water in the suction line.")
        exp = "4.0 / 12.0 / 20.0 mA (±0.05 mA); pump display 0 / 50 / 100 %, run relay closes (P3xx_FB = 1)."
        row([f"AO{d['ch']}", f"`{d['tag']}`", f"`%QW{100 + d['ch']}`", f"-A1.7 / AO{d['ch']}",
             f"-X3:{p} / -X3:{m} (5{31 + 2 * i}/5{32 + 2 * i})", f"{d['dev']} {d['pump']}", test, exp, "☐", "", ""])
    a("")
    a("## 5. Hardwired safety and protection checks (not PLC I/O)")
    a("")
    h2 = ["#", "Function", "Devices / terminals", "Test method", "Expected result", "Pass", "Initials", "Date"]
    row(h2); row(["---"] * len(h2))
    for r_ in (
        ("S1", "E-stop removes 24V-S", "-S0.1, -S0.2, -K0 13-14 / 23-24 (E-06)",
         "Run P-201, a zone valve and F-601 in MANUAL. Press -S0.1; reset; repeat with -S0.2.",
         "Every contactor drops and every valve closes at once; 24V-S = 0 V; ESTOP_OK = 0, A00."),
        ("S2", "Channel monitoring", "-X2:1...6 (wires 601...606)",
         "Lift one channel wire at a time and try -S0R. Bridge the two channels and try -S0R.",
         "-K0 cannot be reset in any case."),
        ("S3", "Monitored reset / EDM", "-S0R, -K201 / -K541 21-22 (E-06)",
         "Lift wire 609 (EDM loop open) and try -S0R; refit. Hold -S0R pressed.",
         "Reset refused with the loop open; a normal reset acts only on release."),
        ("S4", "No automatic restart", "-K0, PLC",
         "Stop a running cycle with -S0.2, release, press -S0R.", "Nothing starts; PLC shows A00; RESET then START needed."),
        ("S5", "End limits stop the drives", "-B512/-B513, -B522/-B523 NC contacts (E-08)",
         "CLIM MANUAL: drive the vent and the net to each end.",
         "Each drive stops at its limit by itself (hardwired), even if the PLC keeps the output on."),
        ("S6", "Reversing interlock", "-K511.1/.2, -K521.1/.2 21-22",
         "With the drive at mid-travel, press the open and close contactors by hand together (de-energised panel: "
         "check the mechanical interlock).", "The second contactor cannot close."),
        ("S7", "Fog pump inlet protection", "-B541 PSL-541 (E-08)",
         "Run P-541 in CLIM MANUAL, close the clean-water supply valve.", "-K541 drops within 2 s; A45 lock-out."),
        ("S8", "Motor protection", "-Q201 ... -Q603",
         "Check each setting against E-02...E-04; trip each with its test button while running.",
         "Motor stops, feedback 0, the motor's discrepancy alarm."),
    ):
        row(list(r_) + ["☐", "", ""])
    a("")
    a("## 6. Remarks and sign-off")
    a("")
    a("| # | Remark / deviation | Action | Closed (initials, date) |")
    a("|---|---|---|---|")
    for _ in range(4):
        a("| | | | |")
    a("")
    a("| Role | Name | Signature | Date |")
    a("|---|---|---|---|")
    a("| Commissioning engineer | | | |")
    a("| Witness (client) | | | |")
    CHECKOUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def di_test(d, addr):
    tag, kind, sense = d["tag"], d["kind"], d.get("sense", "NO")
    if tag == "ESTOP_OK":
        return ("Press -S0.1, reset, press -S0.2, reset.", f"{addr} = 0 while either E-stop is pressed, 1 only after -S0R. HMI: A00.")
    if kind == "int2":
        q, k = d["devs"]
        return (f"Start the drive in MANUAL; then trip {q} with its test button.",
                f"{addr} = 1 with {k} in; 0 with {q} tripped (discrepancy alarm after 2 s).")
    if kind == "int1":
        return (f"{d['devs'][0]} ON, then trip it with its test button.", f"{addr} = 1 healthy, 0 tripped (lock-out alarm).")
    act = d.get("act")
    lifted = f" Lift wire {DI_WIRE[d['ch']]} at -X2:{d['terms'][1]} (wire break)." if sense == "NC" or "_OK" in tag else ""
    if act == "push":
        return (f"Press and release the button.{lifted}",
                f"{addr} = {'1 at rest, 0 while pressed' if sense == 'NC' else '1 only while pressed'}.")
    if act == "float":
        return (f"Lift the float to its normal (wet) position, then let it drop.{lifted}",
                f"{addr} = 1 wet, 0 dry and with the wire lifted.")
    if act == "limit":
        return ("CLIM MANUAL: drive to the limit (or operate the switch by hand, drive isolated).",
                f"{addr} = 1 only at the limit; the drive stops by itself there.")
    if tag == "RAIN_DRY":
        return (f"Wet the detector plate.{lifted}", f"{addr} = 1 dry, 0 wet and with the wire lifted; HMI shows rain.")
    return ("Run the pump in IRR MANUAL with the dosing speed > 0, then switch its MCB off.",
            f"{addr} = 1 while the pump runs, 0 with it stopped or faulted.")


def do_test(d, addr):
    load, tag = d["load"], d["tag"]
    if load == "sol":
        return ("IRR MANUAL: switch the valve on, then off. Repeat and press -S0.1.",
                "Valve opens (indicator / flow), closes when switched off and on E-stop (24V-S off).")
    if load == "lamp":
        return (f"Force {addr} = 1, then 0 (debugger). Repeat with -S0.1 pressed.",
                "Lamp on / off." + (" Stays controllable on E-stop (+24.3)." if tag != "LAMP_GREEN" else
                                     " Off on E-stop (24V-S group)."))
    if load == "coil_sw" and d.get("swkind") == "NO":
        return ("CLIM MANUAL: P-541 on with the clean-water supply open; then close the supply.",
                "-K541 pulls in, fog nozzles spray; drops when the inlet pressure falls.")
    if load == "coil_sw":
        return ("CLIM MANUAL: drive in this direction from mid-travel; press -S0.1 once while moving.",
                "Correct direction; stops at its own end limit and on E-stop.")
    if tag.startswith("P31"):
        return ("IRR MANUAL with P-201 running and flow ≥ 500 L/h, dosing speed 20 %.",
                f"{d['dev']} pulls in, pump runs; drops on E-stop.")
    return ("MANUAL: bump on for 2 s, then off. Repeat and press -S0.1.",
            f"{d['dev']} pulls in, correct rotation, feedback = 1; drops on E-stop.")


# =============================================================================
# CHECKS
# =============================================================================
def consistency_checks() -> list[str]:
    from farmsim import tags
    errs = []
    if E.MISSING:
        errs.append("unresolved cross-references: " + ", ".join(f"{d}:{i}" for d, i in sorted(E.MISSING)))
    if [d["tag"] for d in D.DI] != list(tags.DI_TAGS):
        errs.append("DI list differs from farmsim/tags.py DI_TAGS")
    if [d["tag"] for d in D.DO] != list(tags.DO_TAGS):
        errs.append("DO list differs from farmsim/tags.py DO_TAGS")
    if [d["tag"] for d in D.AI] != list(tags.AI_TAGS[:15]):
        errs.append("AI list differs from farmsim/tags.py AI_TAGS")
    if [d["tag"] for d in D.AO] != list(tags.AO_TAGS):
        errs.append("AO list differs from farmsim/tags.py AO_TAGS")
    drawn = set(E.REG)
    for tm in TERMINALS:
        if (tm[0], tm[1]) not in drawn:
            errs.append(f"terminal {tm[0]}:{tm[1]} is in the terminal plan but not drawn")
    for strip, num in [k for k in E.REG if k[0] in ("X1", "X2", "X3", "X4")]:
        if (strip, num) not in TERM:
            errs.append(f"terminal {strip}:{num} drawn but missing from the terminal plan")
    refs = {r for r, _, _ in D.DEVICES}
    for (dev, _item) in E.REG:
        if dev.startswith("-") and not dev.startswith(("-P1.",)) and dev not in refs:
            errs.append(f"device {dev} drawn but not in the parts list")
    return errs


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    E.PASS = 1
    build_all()
    E.PASS = 2
    E.MISSING.clear()
    sheets = build_all()
    for s in sheets:
        (OUT_DIR / f"{D.DOC_PREFIX}{s.code}.svg").write_text(s.svg(), encoding="utf-8", newline="\n")
    write_index(sheets)
    write_readme()
    write_checkout()
    errs = consistency_checks()
    for e in errs:
        print("CHECK:", e)
    print(f"{len(sheets)} sheets written to {OUT_DIR}; {len(TERMINALS)} terminals; I/O checkout {CHECKOUT_MD.name}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
