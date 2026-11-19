"""Drawing engine for the electrical drawing set: SVG primitives, A3 frame and title block,
IEC 60617 symbols, tables and the two-pass cross-reference register.

Taken from plc-batch-station (tools/drawings/make_drawings.py, T-101) and made project-neutral:
project texts come from ``CFG``, which make_drawings.py fills in before drawing.
SVG user units are millimetres (viewBox 0 0 420 297 = A3 landscape).
"""
from __future__ import annotations

import html
import math  # noqa: F401  (used by sheet code through ``from engine import *``)
import textwrap
from types import SimpleNamespace

CFG = SimpleNamespace(PROJECT="", DOC_PREFIX="", REV="", DATE="", SHEETS=[], CONTACTS={},
                      SUBTITLE=("", "", ""), SET_TITLE="", SCALED={})

W, H = 420.0, 297.0
FX0, FY0, FX1, FY1 = 15.0, 15.0, 405.0, 282.0     # inner frame
TB_Y = 252.0                                      # title block top
NCOL, NROW = 8, 6
CW = (FX1 - FX0) / NCOL                           # 48.75 mm
RH = (FY1 - FY0) / NROW
LW = 0.3      # normal conductor
THIN = 0.2
BUS = 0.45
GREY = "#555"
TEXT_SCALE = 1.08     # all text sizes below are multiplied by this

REG: dict[tuple[str, str], tuple[str, int]] = {}
PASS = 1


def n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def col(x: float) -> int:
    return max(1, min(NCOL, int((x - FX0) // CW) + 1))


def ccx(c: int) -> float:
    """Centre x of column c."""
    return FX0 + (c - 0.5) * CW


def reg(s, dev: str, item: str, x: float) -> None:
    REG[(dev, item)] = (s.code, col(x))


def xr(dev: str, item: str = "main") -> str:
    v = REG.get((dev, item))
    if v is None:
        if PASS == 2:
            MISSING.add((dev, item))
        return "/?"
    return f"/{v[0]}.{v[1]}"


MISSING: set = set()


def tw(s: str, size: float) -> float:
    """Approximate text width (Arial) in mm."""
    w = 0.0
    for ch in s:
        if ch in "il.,:;|!'I1()[] ":
            w += 0.30
        elif ch in "mwMW%":
            w += 0.85
        elif ch.isupper() or ch in "0123456789":
            w += 0.62
        else:
            w += 0.53
    return w * size * TEXT_SCALE


class Sheet:
    def __init__(self, code: str, title: str, index: int):
        self.code, self.title, self.index = code, title, index
        self.o: list[str] = []

    # --- primitives ---------------------------------------------------------
    def line(self, x1, y1, x2, y2, w=LW, dash=None, color="#000"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" '
                      f'stroke="{color}" stroke-width="{n(w)}"{d}/>')

    def poly(self, pts, w=LW, dash=None, fill="none", close=False, color="#000"):
        tag = "polygon" if close else "polyline"
        p = " ".join(f"{n(x)},{n(y)}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<{tag} points="{p}" fill="{fill}" stroke="{color}" stroke-width="{n(w)}"{d}/>')

    def rect(self, x, y, w, h, sw=LW, fill="none", dash=None, color="#000", rx=0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        r = f' rx="{n(rx)}"' if rx else ""
        self.o.append(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"{r} '
                      f'fill="{fill}" stroke="{color}" stroke-width="{n(sw)}"{d}/>')

    def circle(self, cx, cy, r, sw=LW, fill="none", color="#000", dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}" '
                      f'stroke="{color}" stroke-width="{n(sw)}"{d}/>')

    def ellipse(self, cx, cy, rx, ry, sw=THIN, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(ry)}" fill="none" '
                      f'stroke="#000" stroke-width="{n(sw)}"{d}/>')

    def path(self, d, sw=LW, fill="none", dash=None, color="#000"):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{n(sw)}"{da}/>')

    def text(self, x, y, s, size=2.2, anchor="start", bold=False, rot=0, color="#000", italic=False):
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        b = ' font-weight="bold"' if bold else ""
        i = ' font-style="italic"' if italic else ""
        c = f' fill="{color}"' if color != "#000" else ""
        t = f' transform="rotate({n(rot)} {n(x)} {n(y)})"' if rot else ""
        self.o.append(f'<text x="{n(x)}" y="{n(y)}" font-size="{n(size * TEXT_SCALE)}"{a}{b}{i}{c}{t}>'
                      f'{esc(s)}</text>')

    def dot(self, x, y, r=0.6):
        self.o.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}" fill="#000"/>')

    def label(self, x, y, lines, size=2.0, anchor="end", gap=None, bold_first=True):
        """Multi-line label; y = baseline of the first line."""
        g = gap or size * 1.45
        for i, ln in enumerate(lines):
            if ln:
                self.text(x, y + i * g, ln, size if not (i == 0 and bold_first) else size + 0.3,
                          anchor=anchor, bold=(i == 0 and bold_first))

    def para(self, x, y, text, width_mm, size=2.0, gap=None, bold=False):
        """Wrapped paragraph; returns y after the last line."""
        g = gap or size * 1.42
        chars = max(10, int(width_mm / (size * 0.52)))
        for ln in textwrap.wrap(text, chars):
            self.text(x, y, ln, size, bold=bold)
            y += g
        return y

    def svg(self) -> str:
        body = "\n".join(self.o)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" '
                f'viewBox="0 0 420 297">\n'
                f'<title>{esc(CFG.DOC_PREFIX + self.code)} {esc(self.title)}</title>\n'
                f'<style>text{{font-family:Arial,Helvetica,sans-serif;fill:#000}}</style>\n'
                f'<rect x="0" y="0" width="420" height="297" fill="#fff"/>\n'
                f'<g stroke-linecap="round" stroke-linejoin="round">\n{body}\n</g>\n</svg>\n')


# --- frame and title block ----------------------------------------------------
def frame(s: Sheet) -> None:
    s.rect(10, 10, 400, 277, sw=0.5)
    s.rect(FX0, FY0, FX1 - FX0, FY1 - FY0, sw=0.35)
    for i in range(NCOL + 1):
        x = FX0 + i * CW
        s.line(x, 10, x, FY0, 0.25)
        s.line(x, FY1, x, 287, 0.25)
    for i in range(NCOL):
        x = FX0 + (i + 0.5) * CW
        s.text(x, 13.6, str(i + 1), 2.4, anchor="middle")
        s.text(x, 285.9, str(i + 1), 2.4, anchor="middle")
    for j in range(NROW + 1):
        y = FY0 + j * RH
        s.line(10, y, FX0, y, 0.25)
        s.line(FX1, y, 410, y, 0.25)
    for j in range(NROW):
        y = FY0 + (j + 0.5) * RH + 0.9
        s.text(12.5, y, "ABCDEF"[j], 2.4, anchor="middle")
        s.text(407.5, y, "ABCDEF"[j], 2.4, anchor="middle")
    title_block(s)


def title_block(s: Sheet) -> None:
    y0, y1 = TB_Y, FY1
    s.rect(FX0, y0, FX1 - FX0, y1 - y0, sw=0.5, fill="#fff")
    xs = [100, 190, 248, 340]
    for x in xs:
        s.line(x, y0, x, y1, 0.35)
    t = s.text
    # project
    t(17, y0 + 3.6, "Project", 1.7, color=GREY)
    t(17, y0 + 9.2, CFG.PROJECT, 3.6, bold=True)
    t(17, y0 + 13.6, CFG.SUBTITLE[0], 2.0)
    t(17, y0 + 17.0, CFG.SUBTITLE[1], 2.0)
    t(17, y0 + 20.4, CFG.SUBTITLE[2], 2.0)
    t(17, y0 + 26.6, "Symbols IEC 60617 · designations IEC 81346 · IEC 60204-1", 1.7, color=GREY)
    # revisions
    cx = [102, 110, 160, 176]
    t(cx[0], y0 + 3.6, "Rev", 1.7, color=GREY)
    t(cx[1], y0 + 3.6, "Description", 1.7, color=GREY)
    t(cx[2], y0 + 3.6, "Date", 1.7, color=GREY)
    t(cx[3], y0 + 3.6, "By", 1.7, color=GREY)
    for k in range(1, 5):
        s.line(100, y0 + 5 + (k - 1) * 6.25, 190, y0 + 5 + (k - 1) * 6.25, 0.15)
    t(cx[0] + 1, y0 + 9.6, CFG.REV, 2.2, bold=True)
    t(cx[1], y0 + 9.6, "First issue for review", 2.2)
    t(cx[2], y0 + 9.6, CFG.DATE, 2.0)
    # approvals
    t(192, y0 + 3.6, "Name", 1.7, color=GREY)
    t(226, y0 + 3.6, "Date", 1.7, color=GREY)
    for k, lab in enumerate(["Drawn", "Checked", "Approved"]):
        yy = y0 + 10.5 + k * 7.5
        t(192, yy, lab, 2.0)
        s.line(206, yy + 0.6, 223, yy + 0.6, 0.15)
        s.line(226, yy + 0.6, 246, yy + 0.6, 0.15)
    # title
    t(250, y0 + 3.6, "Title", 1.7, color=GREY)
    size = 4.0 if tw(s.title, 4.0) < 86 else 3.4
    t(250, y0 + 12.5, s.title, size, bold=True)
    t(250, y0 + 19.5, CFG.SET_TITLE, 2.2)
    t(250, y0 + 26.6, "Format A3 · scale " + (CFG.SCALED.get(s.code, "none")), 1.8, color=GREY)
    # number
    t(342, y0 + 3.6, "Drawing no.", 1.7, color=GREY)
    t(342, y0 + 10.5, CFG.DOC_PREFIX + s.code, 4.2, bold=True)
    t(342, y0 + 16.5, f"Sheet {s.index + 1} / {len(CFG.SHEETS)}", 2.4)
    t(375, y0 + 16.5, f"Rev. {CFG.REV}", 2.4, bold=True)
    t(342, y0 + 22.0, f"Date {CFG.DATE}", 2.2)
    t(342, y0 + 26.6, "Next: " + (CFG.DOC_PREFIX + CFG.SHEETS[s.index + 1][0] if s.index + 1 < len(CFG.SHEETS) else "-"),
      1.8, color=GREY)


# --- symbols ------------------------------------------------------------------
def arrow(s, x, y, d="r", size=1.6):
    if d == "r":
        pts = [(x, y), (x - size, y - size * 0.45), (x - size, y + size * 0.45)]
    elif d == "l":
        pts = [(x, y), (x + size, y - size * 0.45), (x + size, y + size * 0.45)]
    elif d == "d":
        pts = [(x, y), (x - size * 0.45, y - size), (x + size * 0.45, y - size)]
    else:
        pts = [(x, y), (x - size * 0.45, y + size), (x + size * 0.45, y + size)]
    s.poly(pts, w=0.1, fill="#000", close=True)


def actuator(s, bx, my, x0, kind):
    """Operating device drawn to the left of the leftmost pole at x0."""
    xa = x0 - 7
    s.line(bx, my, xa, my, THIN, dash="0.9 0.6")
    if kind == "push":
        s.poly([(xa - 1, my - 1.6), (xa, my - 1.6), (xa, my + 1.6), (xa - 1, my + 1.6)], w=LW)
    elif kind == "estop":
        s.path(f"M{n(xa)},{n(my - 2.2)} A2.2,2.2 0 0 0 {n(xa)},{n(my + 2.2)} Z", sw=LW)
    elif kind == "manual":
        s.line(xa, my - 1.5, xa, my + 1.5, LW)
    elif kind == "rotary":
        s.line(xa, my - 1.5, xa, my + 1.5, LW)
        s.line(xa - 1.6, my - 1.5, xa, my - 1.5, LW)
        s.line(xa - 1.6, my + 1.5, xa, my + 1.5, LW)
    elif kind == "temp":
        s.rect(xa - 3.2, my - 1.6, 3.2, 3.2, sw=THIN)
        s.text(xa - 1.6, my + 0.75, "θ", 2.2, anchor="middle")
    elif kind == "float":
        s.line(xa, my, xa, my + 2.0, THIN)
        s.circle(xa, my + 3.2, 1.2, sw=THIN)
        s.line(xa - 2.2, my + 3.2, xa + 2.2, my + 3.2, THIN, dash="0.6 0.4")


def contact(s, x, y, kind="NO", L=12.0, func=None, act=None, t1=None, t2=None, w=LW, tside="r"):
    """Contact in vertical orientation, terminals at (x, y) and (x, y+L).
    Returns the blade mid-point (for mechanical linkage)."""
    a = y + L * 0.32
    b = y + L * 0.68
    s.line(x, y, x, a, w)
    s.line(x, b, x, y + L, w)
    if kind == "NO":
        s.line(x, b, x - 2.5, a, w)
        bx = x - 1.25
    else:
        s.line(x, a, x + 2.4, a, w)
        s.line(x, b, x + 2.75, a - 0.6, w)
        bx = x + 1.35
    my = (a + b) / 2
    if func == "contactor":
        s.path(f"M{n(x - 1.1)},{n(a)} A1.1,1.1 0 0 0 {n(x + 1.1)},{n(a)}", sw=THIN)
    elif func == "breaker":
        s.line(x - 0.9, a - 0.9, x + 0.9, a + 0.9, THIN)
        s.line(x - 0.9, a + 0.9, x + 0.9, a - 0.9, THIN)
    elif func == "disconnector":
        s.line(x - 1.2, a, x + 1.2, a, w)
    elif func == "swdisc":
        s.line(x - 1.2, a, x + 1.2, a, w)
        s.circle(x, a + 0.9, 0.8, sw=THIN)
    elif func == "posopen":     # positive opening (arrow in circle simplified)
        s.circle(bx + 1.6, my, 0.9, sw=THIN)
        arrow(s, bx + 1.6, my + 0.55, "d", 0.9)
    if t1:
        if tside == "r":
            s.text(x + 0.8, y + 2.1, t1, 1.6)
        else:
            s.text(x - 0.8, y + 2.1, t1, 1.6, anchor="end")
    if t2:
        if tside == "r":
            s.text(x + 0.8, y + L - 0.5, t2, 1.6)
        else:
            s.text(x - 0.8, y + L - 0.5, t2, 1.6, anchor="end")
    if act:
        actuator(s, bx, my, x, act)
    return bx, my


def prot_boxes(s, x0, my):
    """Thermal + magnetic trip units drawn left of the first pole of a breaker."""
    xl = x0 - 8
    s.line(xl, my - 3.2, xl, my + 3.2, THIN, dash="0.9 0.6")
    s.rect(xl - 5, my - 5.0, 5, 3.6, sw=THIN)
    s.text(xl - 2.5, my - 2.4, "I>", 1.8, anchor="middle")
    s.rect(xl - 5, my + 1.4, 5, 3.6, sw=THIN)
    yb = my + 4.3
    s.poly([(xl - 4.3, yb), (xl - 3.2, yb), (xl - 3.2, yb - 2.2), (xl - 1.8, yb - 2.2),
            (xl - 1.8, yb), (xl - 0.7, yb)], w=THIN)
    return xl


def poles(s, xs, y, kind="NO", L=12.0, func=None, act=None, prot=False, terms=None):
    mids = []
    for i, x in enumerate(xs):
        t1 = t2 = None
        if terms:
            t1, t2 = terms[i]
        mids.append(contact(s, x, y, kind, L, func, None, t1, t2))
    bx_last, my = mids[-1]
    if prot:
        xl = prot_boxes(s, xs[0], my)
        s.line(bx_last, my, xl, my, THIN, dash="0.9 0.6")
    elif len(xs) > 1:
        s.line(bx_last, my, mids[0][0], my, THIN, dash="0.9 0.6")
    if act:
        actuator(s, mids[0][0], my, xs[0], act)
    return my


def fuse(s, x, y, L=12.0):
    s.line(x, y, x, y + L, LW)
    s.rect(x - 1.2, y + L / 2 - 3.5, 2.4, 7, sw=LW, fill="#fff")
    s.line(x, y + L / 2 - 3.5, x, y + L / 2 + 3.5, THIN)


def coil(s, x, y, w=9.0, h=5.0, t1="A1", t2="A2"):
    s.rect(x - w / 2, y, w, h, sw=LW, fill="#fff")
    if t1:
        s.text(x - 0.8, y - 0.8, t1, 1.6, anchor="end")
    if t2:
        s.text(x - 0.8, y + h + 2.2, t2, 1.6, anchor="end")


def diode_v(s, x, yc, up=True, size=1.4):
    """Diode in a vertical conductor, cathode bar on the upper side if up."""
    if up:
        s.poly([(x - size, yc + size * 0.9), (x + size, yc + size * 0.9), (x, yc - size * 0.9)],
               w=THIN, fill="#fff", close=True)
        s.line(x - size, yc - size * 0.9, x + size, yc - size * 0.9, LW)
    else:
        s.poly([(x - size, yc - size * 0.9), (x + size, yc - size * 0.9), (x, yc + size * 0.9)],
               w=THIN, fill="#fff", close=True)
        s.line(x - size, yc + size * 0.9, x + size, yc + size * 0.9, LW)


def suppressor(s, x, ytop, ybot, dx=7.0):
    """Free-wheeling diode in parallel with a DC coil (cathode to +)."""
    xd = x + dx
    yc = (ytop + ybot) / 2
    s.poly([(x, ytop), (xd, ytop), (xd, ybot), (x, ybot)], w=THIN)
    diode_v(s, xd, yc, up=True)
    s.dot(x, ytop, 0.45)
    s.dot(x, ybot, 0.45)


def lamp(s, x, cy, r=3.0):
    s.circle(x, cy, r, sw=LW, fill="#fff")
    d = r * 0.707
    s.line(x - d, cy - d, x + d, cy + d, THIN)
    s.line(x - d, cy + d, x + d, cy - d, THIN)


def motor(s, x, cy, r=8.0, t1="M", t2="3~"):
    s.circle(x, cy, r, sw=LW, fill="#fff")
    s.text(x, cy + 0.6, t1, 4.0, anchor="middle")
    s.text(x, cy + 4.6, t2, 2.2, anchor="middle")


def term(s, x, y, strip, num, side="r", full=True, size=1.7):
    s.circle(x, y, 0.85, sw=THIN, fill="#fff")
    reg(s, strip, num, x)
    lab = f"{strip}:{num}" if full else num
    if side == "r":
        s.text(x + 1.3, y + 0.65, lab, size)
    elif side == "l":
        s.text(x - 1.3, y + 0.65, lab, size, anchor="end")
    elif side == "b":
        s.text(x, y + 2.9, lab, size, anchor="middle")


def wn(s, x, y, txt, side="r", rot=False, size=1.7):
    """Wire number next to a vertical conductor."""
    if rot:
        s.text(x - 0.6, y, txt, size, anchor="middle", rot=-90)
    elif side == "r":
        s.text(x + 0.8, y, txt, size, italic=True)
    else:
        s.text(x - 0.8, y, txt, size, anchor="end", italic=True)


def pe_sym(s, x, y):
    """Protective earth symbol hanging below (x, y)."""
    s.line(x, y, x, y + 2.2, LW)
    for i, half in enumerate((2.0, 1.3, 0.6)):
        yy = y + 2.2 + i * 0.8
        s.line(x - half, yy, x + half, yy, LW)
    s.circle(x, y + 3.0, 2.7, sw=THIN)


def zero_v(s, x, y, txt="0V", xref=None):
    """0 V reference tag below (x, y)."""
    s.line(x, y, x, y + 2.5, LW)
    s.line(x - 1.8, y + 2.5, x + 1.8, y + 2.5, 0.5)
    s.text(x + 2.4, y + 3.2, txt, 1.9, bold=True)
    if xref:
        s.text(x + 2.4 + tw(txt, 1.9) + 1.2, y + 3.2, xref, 1.7)


def bus_in(s, x, y, name, xref, x_end, size=2.1):
    """Potential entering from another sheet at the left: name, xref, line."""
    s.line(x, y, x_end, y, BUS)
    s.text(x - 1.2, y + 0.75, name, size, anchor="end", bold=True)
    s.text(x + 1.0, y - 0.8, "from " + xref, 1.6, color=GREY)


def drop_tag(s, x, y, name, xref, size=2.0):
    """Potential arriving from the top (vertical line downwards from y)."""
    arrow(s, x, y + 2.2, "d", 1.4)
    s.text(x + 1.4, y + 0.6, name, size, bold=True)
    s.text(x + 1.4 + tw(name, size) + 1.0, y + 0.6, xref, 1.7, color=GREY)


def mini_contact(s, x, y, kind, h=3.6):
    a, b = y + h * 0.3, y + h * 0.7
    s.line(x, y, x, a, THIN)
    s.line(x, b, x, y + h, THIN)
    if kind == "NO":
        s.line(x, b, x - 1.0, a, THIN)
    else:
        s.line(x, a, x + 0.9, a, THIN)
        s.line(x, b, x + 1.1, a - 0.3, THIN)


def mirror(s, x, y, dev):
    """Contact mirror below a coil: list of contacts with their location."""
    s.text(x - 3, y, "contacts:", 1.6, color=GREY)
    yy = y + 1.4
    for t1, t2, kind in CFG.CONTACTS[dev]:
        mini_contact(s, x - 1, yy, kind)
        s.text(x + 1.6, yy + 2.6, f"{t1}-{t2}", 1.85)
        key = (dev, f"{t1}-{t2}")
        loc = xr(*key) if key in REG else ("spare" if PASS == 2 else "/?")
        s.text(x + 9.5, yy + 2.6, loc, 1.85)
        yy += 4.6
    return yy


def boxed(s, x, y, w, h, lines, size=2.0, sw=LW, dash=None, fill="#fff", anchor="start", pad=1.6):
    s.rect(x, y, w, h, sw=sw, dash=dash, fill=fill)
    g = size * 1.45
    yy = y + pad + size
    for i, ln in enumerate(lines):
        bold = i == 0
        if anchor == "middle":
            s.text(x + w / 2, yy, ln, size + (0.3 if bold else 0), anchor="middle", bold=bold)
        else:
            s.text(x + pad, yy, ln, size + (0.3 if bold else 0), bold=bold)
        yy += g


def table(s, x, y, widths, rows, size=1.9, rh=4.3, header=True, title=None):
    """Simple ruled table. rows[0] is the header if header=True. Returns bottom y."""
    if title:
        s.text(x, y - 1.6, title, 2.6, bold=True)
    total = sum(widths)
    for r, row in enumerate(rows):
        yy = y + r * rh
        if r == 0 and header:
            s.rect(x, yy, total, rh, sw=THIN, fill="#e8e8e8")
        xx = x
        for c, cell in enumerate(row):
            s.text(xx + 1.0, yy + rh * 0.72, cell, size, bold=(r == 0 and header))
            xx += widths[c]
        s.line(x, yy + rh, x + total, yy + rh, 0.12)
    yb = y + len(rows) * rh
    s.rect(x, y, total, yb - y, sw=0.3)
    xx = x
    for wdt in widths[:-1]:
        xx += wdt
        s.line(xx, y, xx, yb, 0.12)
    return yb


def notes(s, x, y, items, width, size=2.0, title="Notes"):
    s.text(x, y, title, 2.4, bold=True)
    y += 4.0
    for i, it in enumerate(items, 1):
        s.text(x, y, f"{i}.", size)
        y = s.para(x + 3.4, y, it, width - 3.4, size) + 0.8
    return y



# legend drawing functions (cx, top)
def _lg_no(s, x, y):
    s.line(x, y, x, y + 1.5); contact(s, x, y + 1.5, "NO", 11, t1="13", t2="14")


def _lg_nc(s, x, y):
    s.line(x, y, x, y + 1.5); contact(s, x, y + 1.5, "NC", 11, t1="11", t2="12")


def _lg_pbno(s, x, y):
    contact(s, x + 3, y + 1, "NO", 12, act="push")


def _lg_pbnc(s, x, y):
    contact(s, x + 3, y + 1, "NC", 12, act="push")


def _lg_estop(s, x, y):
    contact(s, x + 3, y + 1, "NC", 12, act="estop", func="posopen")


def _lg_cont(s, x, y):
    poles(s, [x - 4, x + 2, x + 8], y + 1, "NO", 12, func="contactor")


def _lg_brk(s, x, y):
    poles(s, [x, x + 6, x + 12], y + 1, "NO", 12, func="breaker", prot=True)


def _lg_swd(s, x, y):
    poles(s, [x - 2, x + 4, x + 10], y + 1, "NO", 12, func="swdisc", act="rotary")


def _lg_fuse(s, x, y):
    fuse(s, x, y + 1, 12)


def _lg_coil(s, x, y):
    s.line(x, y + 1, x, y + 4.5); coil(s, x, y + 4.5); s.line(x, y + 9.5, x, y + 13)


def _lg_coild(s, x, y):
    s.line(x - 3, y + 1, x - 3, y + 4.5); coil(s, x - 3, y + 4.5); s.line(x - 3, y + 9.5, x - 3, y + 13)
    suppressor(s, x - 3, y + 2.5, y + 11.5, 8)


def _lg_lamp(s, x, y):
    s.line(x, y + 1, x, y + 4); lamp(s, x, y + 7); s.line(x, y + 10, x, y + 13)


def _lg_motor(s, x, y):
    motor(s, x, y + 7.5, 6.5)


def _lg_heater(s, x, y):
    s.rect(x - 8, y + 1.5, 16, 11, sw=THIN, dash="1 0.6")
    for dx in (-4, 0, 4):
        s.rect(x + dx - 0.9, y + 3, 1.8, 6, sw=LW)
    s.line(x - 4, y + 9, x + 4, y + 9, THIN)


def _lg_thy(s, x, y):
    s.rect(x - 7, y + 1, 14, 12, sw=LW)
    thyristor_pair(s, x, y + 7)


def _lg_psu(s, x, y):
    psu_box(s, x - 8, y + 1.5, 16, 11)


def _lg_term(s, x, y):
    s.line(x - 6, y + 7, x + 6, y + 7); term(s, x, y + 7, "X2", "11", side="b")


def _lg_junction(s, x, y):
    s.line(x - 7, y + 4, x + 7, y + 4); s.line(x - 3, y + 4, x - 3, y + 12); s.dot(x - 3, y + 4)
    s.line(x - 7, y + 9, x + 7, y + 9); s.line(x + 4, y + 1, x + 4, y + 12)


def _lg_pe(s, x, y):
    pe_sym(s, x, y + 3)


def _lg_0v(s, x, y):
    zero_v(s, x - 3, y + 5, "0V", "/E-01.3")


def _lg_float(s, x, y):
    contact(s, x + 3, y + 1, "NC", 12, act="float")


def _lg_thermo(s, x, y):
    contact(s, x + 3, y + 1, "NC", 12, act="temp")


def _lg_tx(s, x, y):
    s.rect(x - 7, y + 1.5, 14, 7, sw=LW)
    s.text(x, y + 6.0, "4-20 mA", 1.6, anchor="middle")
    s.line(x - 4, y + 8.5, x - 4, y + 13); s.line(x + 4, y + 8.5, x + 4, y + 13)
    s.text(x - 5, y + 11.5, "+", 1.8, anchor="end"); s.text(x + 5, y + 11.5, "-", 1.8)


def _lg_shield(s, x, y):
    s.line(x - 3, y + 1, x - 3, y + 13); s.line(x + 3, y + 1, x + 3, y + 13)
    s.ellipse(x, y + 7, 6, 1.6, dash="0.8 0.5")
    s.line(x + 6, y + 7, x + 9, y + 7, THIN); s.line(x + 9, y + 7, x + 9, y + 9, THIN)


def _lg_xref(s, x, y):
    s.line(x - 10, y + 5, x + 4, y + 5, BUS); arrow(s, x + 5.6, y + 5, "r")
    s.text(x - 10, y + 3.8, "+24.2", 1.9, bold=True)
    s.text(x - 10, y + 9.2, "to /E-04.1", 1.7)


def _lg_diode(s, x, y):
    s.line(x, y + 1, x, y + 13, THIN); diode_v(s, x, y + 7)




def thyristor_pair(s, x, yc):
    """Anti-parallel thyristors in a vertical conductor at x, centred yc."""
    s.line(x, yc - 4.5, x, yc - 3, THIN)
    s.line(x, yc + 3, x, yc + 4.5, THIN)
    s.line(x - 1.8, yc - 3, x + 1.8, yc - 3, THIN)
    s.line(x - 1.8, yc + 3, x + 1.8, yc + 3, THIN)
    for dx, up in ((-1.8, False), (1.8, True)):
        xx = x + dx
        s.line(xx, yc - 3, xx, yc - 1.1, THIN)
        s.line(xx, yc + 1.1, xx, yc + 3, THIN)
        diode_v(s, xx, yc, up=up, size=1.0)
    s.line(x - 1.8, yc + 0.9, x - 3.0, yc + 2.0, THIN)
    s.line(x + 1.8, yc - 0.9, x + 3.0, yc - 2.0, THIN)


def psu_box(s, x, y, w, h):
    s.rect(x, y, w, h, sw=LW, fill="#fff")
    s.line(x, y + h, x + w, y, THIN)
    s.text(x + w * 0.27, y + h * 0.42, "~", 2.8, anchor="middle")
    s.text(x + w * 0.73, y + h * 0.88, "=", 2.8, anchor="middle")

