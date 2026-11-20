// Runs the real GH-1 PLC program (greenhouse.st in the ST interpreter) and the plant model in Pyodide.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js");

let demo = null, speed = 20, lastPost = 0, simAt = 0, wallAt = 0, achieved = 0;

async function boot() {
  postMessage({status: "Loading Python (Pyodide)…"});
  const py = await loadPyodide();
  postMessage({status: "Loading the PLC program and the plant model…"});
  const files = (await (await fetch("py/files.txt")).text()).trim().split(/\r?\n/);
  for (const f of files) {
    py.FS.mkdirTree("/gh1/" + f.split("/").slice(0, -1).join("/"));
    py.FS.writeFile("/gh1/" + f, await (await fetch("py/" + f)).text());
  }
  postMessage({status: "Compiling greenhouse.st…"});
  py.runPython("import sys; sys.path.insert(0, '/gh1')\nfrom farmsim.webdemo import Demo, meta\ndemo = Demo('07:00')");
  demo = py.globals.get("demo");
  postMessage({meta: JSON.parse(py.runPython("meta()"))});
  wallAt = performance.now();
  simAt = 0;
  loop();
}

function loop() {
  const t0 = performance.now();
  if (speed === "max") { while (performance.now() - t0 < 40) demo.run(20); }
  else if (speed > 0) demo.run(speed);                 // `speed` scans of 50 ms per 50 ms of wall time
  const now = performance.now();
  if (now - lastPost > 100) {
    lastPost = now;
    const s = JSON.parse(demo.state());
    if (now - wallAt > 2000) {                         // achieved speed over the last ~2 s
      achieved = (s.sim_s - simAt) / ((now - wallAt) / 1000);
      simAt = s.sim_s; wallAt = now;
    }
    s.achieved = achieved;
    postMessage({state: s});
  }
  setTimeout(loop, Math.max(0, 50 - (performance.now() - t0)));
}

onmessage = e => {
  const m = e.data;
  if (m.cmd === "speed") { speed = m.value; return; }
  if (!demo) return;
  const reply = JSON.parse(demo.command(JSON.stringify(m)));
  postMessage({reply, cmd: m});
};

boot().catch(err => postMessage({error: String(err)}));
