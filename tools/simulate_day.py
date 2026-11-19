"""Simulate one day on the in-process bench and summarise it (PRD NFR-09, acceptance 10.2).

    py tools/simulate_day.py [--scenario clear] [--start 05:00] [--end 19:00] [--csv out.csv]

Prints hourly climate and irrigation figures, state changes and alarms.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmsim.bench import Bench  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="clear")
    ap.add_argument("--start", default="05:00")
    ap.add_argument("--end", default="19:00")
    ap.add_argument("--csv")
    a = ap.parse_args(argv)
    hh, mm = (int(x) for x in a.end.split(":"))
    end_min = hh * 60 + mm
    b = Bench(clock=a.start, scenario=a.scenario)
    b.record_every = 60.0
    b.run(2.0)
    b.hmi("reset")
    t0 = time.perf_counter()
    clim_changes, last_clim, last_hour = [], b.clim, -1
    max_t, cyc_ok = 0.0, 0
    while b.plant.clock_min < end_min:
        b.run(10.0)
        if b.clim != last_clim:
            clim_changes.append((b.plant.clock_min, last_clim, b.clim))
            last_clim = b.clim
        max_t = max(max_t, b.plant.t_in)
        h = b.plant.clock_min // 60
        if h != last_hour:
            last_hour = h
            p, st = b.plant, b.status
            print(f"{h:02d}:00 out {p.wx.t_out:4.1f} rad {p.wx.rad:4.0f} | in {p.t_in:4.1f} RH {p.rh_in:4.1f} "
                  f"VPD {p.vpd:4.2f} CO2 {p.co2:4.0f} | vent {p.vent_pos:5.1f} net {p.net_pos:5.1f} "
                  f"clim {st['clim_state_name']:<10} fans {st['fan_stage']} | cycles {st['cycles_day']:2d} "
                  f"water {st['water_day']:5.0f} L drain {st['drain_day']:4.1f} % | {b.alarm_list()}")
    st = b.status
    print(f"\nsimulated {b.t / 3600:.1f} h in {time.perf_counter() - t0:.0f} s")
    print(f"max greenhouse temperature {max_t:.1f} degC")
    print(f"climate state changes: {len(clim_changes)}")
    for m, f, t in clim_changes:
        print(f"  {m // 60:02d}:{m % 60:02d}  {f} -> {t}")
    print(f"cycles {st['cycles_day']}, water {st['water_day']:.0f} L, drain {st['drain_day']:.1f} %, "
          f"alarms latched {b.alarm_list()}")
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(b.history[0]))
            w.writeheader()
            w.writerows(b.history)


if __name__ == "__main__":
    main()
