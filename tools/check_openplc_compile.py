"""Compile the PLC program with STruC++, the OpenPLC v4 compiler, and cross-check it.

This is FAT row OPL-01. It proves that ``plc/greenhouse.st`` compiles with the real
OpenPLC toolchain, and that STruC++ and this project's ST VM agree on:

* every located variable (name and address, e.g. ``ESTOP_OK AT %IX100.0``)
* the task interval (50 ms)

Usage::

    python tools/check_openplc_compile.py [--strucpp PATH]

STruC++ is found from ``--strucpp``, the ``STRUCPP`` environment variable, ``PATH``, or a
release unpacked under ``.tools/`` (see docs/openplc.md). Exit code 0 = pass.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from farmsim.stvm import STMachine  # noqa: E402

PROGRAM = ROOT / "plc" / "greenhouse.st"


def find_strucpp(explicit: str | None) -> str | None:
    for cand in (explicit, os.environ.get("STRUCPP"), shutil.which("strucpp")):
        if cand and Path(cand).is_file():
            return cand
    exe = "strucpp.exe" if os.name == "nt" else "strucpp"
    hits = sorted(glob.glob(str(ROOT / ".tools" / "strucpp-*" / "**" / exe), recursive=True))
    return hits[-1] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strucpp", help="path to the strucpp executable")
    args = ap.parse_args()

    exe = find_strucpp(args.strucpp)
    if not exe:
        print("FAIL: STruC++ not found. See docs/openplc.md, section 2.")
        return 2

    version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"compiler : {version} ({exe})")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "greenhouse.cpp"
        res = subprocess.run([exe, str(PROGRAM), "-o", str(out)], capture_output=True, text=True)
        log = (res.stdout + res.stderr).strip()
        cpp = out.read_text(encoding="utf8") if out.exists() else ""

    problems: list[str] = []
    if res.returncode != 0:
        problems.append(f"compile failed (exit {res.returncode})")
    warnings = [ln for ln in log.splitlines() if re.search(r"(?i)\bwarning\b", ln)]
    problems += [f"compiler warning: {w}" for w in warnings]

    # Located variables, as STruC++ generated them: "// NAME AT %IX100.0"
    gen = {addr.upper(): name.upper()
           for name, addr in re.findall(r"//\s*(\w+)\s+AT\s+(%[A-Z]{2}[\d.]+)", cpp)}
    vm = STMachine(PROGRAM.read_text(encoding="utf8"))
    ours = {addr.upper(): name.upper() for addr, name in vm.located.items()}
    for addr in sorted(set(gen) | set(ours)):
        if gen.get(addr) != ours.get(addr):
            problems.append(f"located variable differs at {addr}: "
                            f"STruC++={gen.get(addr)} VM={ours.get(addr)}")

    # Task interval: TaskInstance("MAINTASK", 50000000LL, ...) in nanoseconds
    m = re.search(r'TaskInstance\("(\w+)",\s*(\d+)LL', cpp)
    task_ms = int(m.group(2)) / 1e6 if m else None
    if task_ms != vm.cycle_ms:
        problems.append(f"task interval differs: STruC++={task_ms} ms VM={vm.cycle_ms} ms")

    print(f"program  : {PROGRAM.relative_to(ROOT)}")
    print(f"located  : {len(gen)} variables, all match the VM" if gen == ours and gen
          else f"located  : STruC++ {len(gen)}, VM {len(ours)}")
    print(f"task     : {m.group(1) if m else '?'} every {task_ms} ms")
    if problems:
        print("\n".join(["", "FAIL"] + [f"  - {p}" for p in problems]))
        if log:
            print("\ncompiler output:\n" + log)
        return 1
    print("\nPASS: compiles with no errors or warnings (FAT OPL-01)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
