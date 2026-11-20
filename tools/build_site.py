"""Copy the Python package and the PLC program into site/py/ for the browser demo (Pyodide).

    python tools/build_site.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["farmsim/__init__.py", "farmsim/stvm.py", "farmsim/tags.py", "farmsim/weather.py", "farmsim/plant.py",
         "farmsim/bench.py", "farmsim/faults.py", "farmsim/crops.py", "farmsim/webdemo.py", "plc/greenhouse.st"]

if __name__ == "__main__":
    out = ROOT / "site" / "py"
    shutil.rmtree(out, ignore_errors=True)
    for f in FILES:
        (out / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, out / f)
    (out / "files.txt").write_text("\n".join(FILES) + "\n", newline="\n")
    print(f"copied {len(FILES)} files to {out.relative_to(ROOT)}")
