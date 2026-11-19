"""Dosing-loop tuning sweep (FDS 7.1).

Runs one irrigation cycle per gain set on the in-process bench and reports the time to
reach the band, the EC/pH range while pumping (overshoot) and the steady-state range
during SHOT (each zone after 30 s).

    py tools/tune_dosing.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmsim.bench import ST_FILE, Bench  # noqa: E402
from farmsim.stvm import STMachine  # noqa: E402

BASE = ST_FILE.read_text(encoding="utf-8")


def with_consts(**kw) -> str:
    s = BASE
    for k, v in kw.items():
        s, n = re.subn(rf"({k}\s*: REAL := )[0-9.]+", rf"\g<1>{v}", s)
        assert n == 1, k
    return s


def run(**kw) -> dict:
    b = Bench(vm=STMachine(with_consts(**kw), strict=False), clock="06:29")
    b.run_until(lambda b: b.step == 10, 200)
    t0, inband_t, holds, last = b.t, None, 0, 10
    ec_rng, ph_rng, ec_ss, ph_ss = [9.0, 0.0], [14.0, 0.0], [9.0, 0.0], [14.0, 0.0]
    while b.t - t0 < 700 and b.step != 0:
        b.tick()
        p = b.plant
        if b.step == 20 and inband_t is None:
            inband_t = round(b.t - t0, 1)
        if b.step == 25 and last != 25:
            holds += 1
        last = b.step
        if p.q_pump > 0.1:
            ec_rng = [min(ec_rng[0], p.ec_true), max(ec_rng[1], p.ec_true)]
            ph_rng = [min(ph_rng[0], p.ph_true), max(ph_rng[1], p.ph_true)]
        if b.step == 20 and b.vm["zone_open_secs"] > 30:
            ec_ss = [min(ec_ss[0], p.ec_true), max(ec_ss[1], p.ec_true)]
            ph_ss = [min(ph_ss[0], p.ph_true), max(ph_ss[1], p.ph_true)]
    r2 = lambda xs: [round(x, 2) for x in xs]  # noqa: E731
    return dict(to_shot_s=inband_t, ec=r2(ec_rng), ph=r2(ph_rng), ec_shot=r2(ec_ss), ph_shot=r2(ph_ss),
                holds=holds, alarms=b.alarm_list())


if __name__ == "__main__":
    # (EC_KP, EC_TI, PH_KP, PH_TI, EC_IZONE, PH_IZONE); the first row is the chosen tuning
    for g in [(8, 12, 5, 12, 0.5, 0.5), (10, 10, 6, 10, 0.4, 0.4), (6, 8, 4, 8, 0.5, 0.5), (4, 15, 3, 20, 0, 0)]:
        print(g, run(EC_KP=float(g[0]), EC_TI=float(g[1]), PH_KP=float(g[2]), PH_TI=float(g[3]),
                     EC_IZONE=float(g[4]), PH_IZONE=float(g[5])))
