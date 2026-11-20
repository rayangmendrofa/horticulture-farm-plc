// GH-1 greenhouse page: draws the farm (original pixel art, all drawn in code) and drives the worker.
"use strict";
const $ = id => document.getElementById(id);
const esc = t => String(t).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const fx = (v, d = 1) => v == null || isNaN(v) ? "--" : Number(v).toFixed(d);
const cv = $("farm"), g = cv.getContext("2d");
g.imageSmoothingEnabled = false;
let S = null, META = null, sel = 0, robotX = 120, dragging = null, speed = 20;
const worker = new Worker("worker.js");
const send = m => worker.postMessage(m);

// ---------------------------------------------------------------- drawing helpers
const R = (x, y, w, h, c) => { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); };
const mix = (a, b, t) => {
  const p = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
};
const hash = n => { n = Math.sin(n * 12.9898) * 43758.5453; return n - Math.floor(n); };
const BED_Y = [56, 86, 116, 146], BED_X0 = 86, BED_X1 = 292, PATH_Y = 172;
const LEAF = {tomato: "#3e8f3a", chili: "#2f7a34", cucumber: "#3a9a42", melon: "#5aa54a", strawberry: "#3d8f45",
              lettuce: "#93d354", kangkung: "#3fae5a"};
const FLOWER = {tomato: "#f5d442", chili: "#f4f4f0", cucumber: "#f5d442", melon: "#f5d442", strawberry: "#f4f4f0"};

function sky(t, s) {
  const m = s.clock_min, wx = s.weather;
  const day = m >= 360 && m <= 1080, k = day ? Math.sin(Math.PI * (m - 360) / 720) : 0;
  const clear = {clear: "#79b8e8", cloudy: "#8fa3b3", rain: "#62707d", storm: "#3c4652"}[wx.look] || "#79b8e8";
  const night = "#0b1430", dawn = "#e98c5d";
  let c = day ? (k < 0.25 ? mix(dawn, clear, k / 0.25) : clear) : night;
  if (wx.look === "storm" && hash(Math.floor(t / 90)) > 0.97) c = "#e8eef5";           // lightning
  R(0, 0, 320, 40, c);
  if (day) {
    const x = 10 + 300 * (m - 360) / 720, y = 30 - 24 * k;
    if (wx.look === "clear" || wx.look === "cloudy") { R(x - 3, y - 3, 7, 7, "#ffe27a"); R(x - 2, y - 4, 5, 9, "#ffe27a"); }
  } else {
    const x = 20 + 280 * (((m + 1440 - 1080) % 1440) / 720), y = 10;
    R(x, y, 4, 4, "#e8e8f0"); R(x + 2, y, 2, 2, night);
    for (let i = 0; i < 18; i++) R(hash(i) * 320, hash(i + 50) * 34, 1, 1, "#c8d0e8");
  }
  if (wx.look !== "clear") {
    const n = {cloudy: 5, rain: 7, storm: 9}[wx.look];
    for (let i = 0; i < n; i++) {
      const x = ((hash(i) * 360 + t * (6 + wx.wind) / 4000) % 380) - 40, y = 4 + hash(i + 9) * 20;
      const cc = wx.look === "cloudy" ? "#e4e9ee" : "#9aa5af";
      R(x, y, 22, 6, cc); R(x + 4, y - 3, 12, 4, cc);
    }
  }
  R(0, 40, 320, 160, "#4e7a3a");
  for (let i = 0; i < 140; i++) R(hash(i + 3) * 320, 40 + hash(i + 7) * 160, 1, 2, "#5d8a45");
}

function rain(t, s) {
  if (!s.weather.rain) return;
  g.globalAlpha = 0.55;
  for (let i = 0; i < 70; i++) {
    const x = (hash(i) * 330 + t * 0.06) % 330 - 5, y = (hash(i + 20) * 200 + t * 0.25) % 200;
    R(x, y, 1, 3, "#b9d4ee");
  }
  g.globalAlpha = 1;
}

function windsock(t, s) {
  const w = Math.min(1, s.weather.wind / 15);
  R(56, 22, 1, 18, "#cfd3d6");
  for (let i = 0; i < 4; i++) {
    const len = 2 + 2 * w, y = 22 + i * 0.4 + (1 - w) * i * 1.4 + Math.sin(t / 150 + i) * w;
    R(57 + i * len, y, len + 0.5, 2, i % 2 ? "#f2f2f2" : "#e35a2c");
  }
}

function plantSprite(x, cy, z, i, t) {
  const crop = z.crop, m = z.maturity / 100, hp = z.health / 100, seed = hash(i * 7.3 + BED_Y.indexOf(cy - 9) * 31);
  if (z.stage === "dead") { R(x - 2, cy - 1, 5, 3, "#6b4a2a"); return; }
  const leaf = mix(LEAF[crop], "#a08a3c", Math.min(1, (1 - hp) * 0.9));
  const dark = mix(leaf, "#0f2a12", 0.35);
  const s = Math.max(1, Math.round(1 + m * 5 + (seed - 0.5)));
  if (z.stage === "seedling") { R(x, cy - 1, 1, 3, leaf); R(x - 1, cy - 1, 1, 1, leaf); R(x + 1, cy - 2, 1, 1, leaf); return; }
  if (crop === "lettuce" || crop === "kangkung") {
    R(x - s, cy - s + 1, 2 * s + 1, 2 * s - 1, dark);
    R(x - s + 1, cy - s, 2 * s - 1, 2 * s + 1, dark);
    R(x - s + 1, cy - s + 1, 2 * s - 1, 2 * s - 1, leaf);
    if (crop === "lettuce") R(x - 1, cy - 1, 3, 3, mix(leaf, "#e9f7c4", 0.5));
    else { R(x - s, cy, 2 * s + 1, 1, dark); R(x, cy - s, 1, 2 * s + 1, dark); }
    return;
  }
  const wide = crop === "melon" ? 2 : 1, low = crop === "strawberry" ? 0.6 : 1;
  const rw = Math.round(s * wide), rh = Math.max(1, Math.round(s * low));
  const light = mix(leaf, "#e9f7c4", 0.35);
  for (let k = 0; k < 4 + 3 * rw; k++) {                  // a bush of small two-tone leaves
    const lx = x + (hash(seed * 13 + k) - 0.5) * 2 * rw, ly = cy + (hash(seed * 17 + k) - 0.5) * 2 * rh;
    R(lx - 1, ly - 1, 3, 3, dark); R(lx - 1, ly - 1, 2, 2, leaf); R(lx - 1, ly - 1, 1, 1, light);
  }
  if (z.stage === "flowering") for (let k = 0; k < 3; k++) R(x - rw + 1 + hash(seed + k) * 2 * rw, cy - rh + 1 + hash(seed + k + 4) * 2 * rh, 1, 1, FLOWER[crop]);
  if (z.stage === "ripe") {
    const col = META.crops[crop].colour;
    if (crop === "melon") { R(x - 2, cy - 1, 4, 3, col); R(x - 1, cy - 2, 2, 5, col); }
    else if (crop === "cucumber") for (let k = 0; k < 3; k++) R(x - rw + 1 + hash(seed + k) * 2 * rw, cy - 1 + k, 3, 1, "#1e5d22");
    else for (let k = 0; k < 4; k++) R(x - rw + 1 + hash(seed + k) * (2 * rw - 1), cy - rh + 1 + hash(seed + k + 4) * (2 * rh - 1), crop === "chili" ? 1 : 2, crop === "chili" ? 2 : 1, col);
  }
}

function greenhouse(t, s) {
  const p = s.plc, run = new Set(p.running);
  R(70, 42, 238, 150, "#d7dde2");                  // frame
  R(72, 44, 234, 146, "#36414a");                  // floor
  R(73, 52, 3, 130, run.has("p531") ? "#5aa9e6" : "#c9b48a");   // pad wall
  for (let y = 54; y < 180; y += 4) R(73, y, 3, 1, run.has("p531") ? "#7fc0ee" : "#b39c70");
  // ridge vent: dark gap opens with the vent position
  R(78, 44, 224, 5, "#9aa6b0");
  R(80, 45, 220 * p.vent / 100, 3, "#1a2026");
  // beds
  for (let i = 0; i < 4; i++) {
    const y = BED_Y[i], z = s.zones[i];
    R(BED_X0 - 2, y - 1, BED_X1 - BED_X0 + 4, 20, i === sel ? "#f2d06b" : "#2b3238");
    R(BED_X0, y, BED_X1 - BED_X0, 18, "#5b3b26");
    for (let k = 0; k < 20; k++) R(BED_X0 + hash(k + i * 40) * (BED_X1 - BED_X0), y + hash(k + 3 + i * 40) * 18, 1, 1, "#6e4a31");
    R(BED_X0, y + 9, BED_X1 - BED_X0, 1, "#8a949c");                 // drip line
    if (z.watering) for (let k = 0; k < 14; k++) R(BED_X0 + ((k * 15 + t * 0.03) % (BED_X1 - BED_X0)), y + 9, 2, 1, "#7fd0ff");
    if (z.crop) for (let k = 0; k < 9; k++) plantSprite(BED_X0 + 11 + k * 23, y + 9, z, k, t);
    R(78, y + 5, 6, 8, "#1d232a");
    g.fillStyle = "#e8ecef"; g.font = "6px monospace"; g.fillText(String(i + 1), 79, y + 11);
  }
  // fog
  if (run.has("p541")) {
    g.globalAlpha = 0.35;
    for (let k = 0; k < 60; k++) R(80 + (hash(k) * 220 + t * 0.01) % 220, 50 + (hash(k + 9) * 120 + Math.sin(t / 500 + k) * 3), 2, 2, "#f4f8fb");
    g.globalAlpha = 1;
  }
  // fans + air flow
  const fans = ["f601", "f602", "f603"];
  fans.forEach((f, j) => {
    const y = 70 + j * 40, on = run.has(f);
    R(302, y - 5, 6, 11, "#5b646c");
    const a = on ? Math.floor(t / 60) % 2 : 0;
    R(303, y - 3 + a, 4, 1, "#d7dde2"); R(304 + a, y - 4, 1, 9, "#d7dde2");
    if (on) for (let k = 0; k < 4; k++) R(90 + ((k * 55 + t * 0.06) % 200), y + 2, 6, 1, "#7fd0ff80");
  });
  // path, robot
  R(84, PATH_Y - 3, 212, 14, "#7b8288");
  const target = BED_X0 + 20 + sel * 4 + (BED_X1 - BED_X0 - 40) * 0.5;
  robotX += Math.sign(target - robotX) * Math.min(Math.abs(target - robotX), 0.6);
  robot(robotX, PATH_Y + 2, t);
  // shade net (dither over the house)
  if (p.net !== "retracted") {
    g.globalAlpha = p.net === "deployed" ? 0.38 : 0.18;
    for (let y = 44; y < 190; y += 2) for (let x = 72 + (y % 4); x < 306; x += 4) R(x, y, 2, 1, "#0d1014");
    g.globalAlpha = 1;
  }
}

function robot(x, y, t) {
  const b = Math.round(Math.sin(t / 180));
  R(x - 4, y - 6 + b, 9, 6, "#3ab0a5"); R(x - 3, y - 9 + b, 7, 4, "#2b8f86");
  R(x + 1, y - 8 + b, 2, 2, "#f6f2b0"); R(x, y - 11 + b, 1, 2, "#cfd3d6"); R(x - 1, y - 12 + b, 3, 1, "#e35a2c");
  R(x - 4, y, 3, 2, "#1d232a"); R(x + 2, y, 3, 2, "#1d232a");
}

function waterSide(t, s) {
  const p = s.plc, run = new Set(p.running), flow = p.flow > 50;
  // tank T-201
  R(6, 58, 26, 44, "#c3c9ce"); R(8, 60, 22, 40, "#1d232a");
  const h = 40 * p.level / 100; R(8, 100 - h, 22, h, "#3d84c4"); R(8, 100 - h, 22, 1, "#7fc0ee");
  g.fillStyle = "#e8ecef"; g.font = "6px monospace"; g.fillText("T201", 8, 55);
  // pipes
  const pipe = (x, y, w, hh) => R(x, y, w, hh, "#8a949c");
  pipe(18, 102, 2, 8); pipe(18, 108, 50, 2); pipe(66, 63, 2, 103);
  for (const y of BED_Y) pipe(66, y + 9, BED_X0 - 66, 1);
  if (flow) for (let k = 0; k < 8; k++) R(20 + ((k * 7 + t * 0.03) % 46), 108, 2, 2, "#7fd0ff");
  // pump
  const on = run.has("p201"), a = on ? Math.floor(t / 70) % 2 : 0;
  R(36, 104, 9, 9, on ? "#e8ecef" : "#5b646c"); R(39 + a, 106, 3 - a, 5, "#1d232a");
  // dosing jugs
  const jug = (x, c, v) => { R(x, 120, 8, 12, "#c3c9ce"); R(x + 1, 121, 6, 10, "#1d232a"); R(x + 1, 131 - v / 10, 6, v / 10, c); };
  jug(6, "#6cc37a", p.dose[0]); jug(16, "#b07ad8", p.dose[1]); jug(26, "#e8963c", p.dose[2]);
  g.fillStyle = "#e8ecef"; g.font = "5px monospace"; g.fillText("A  B ac", 7, 139);
  if (p.outputs.XV301 && flow) for (let k = 0; k < 4; k++) R(40, 64 + ((k * 9 + t * 0.03) % 40), 1, 2, "#7fd0ff");
  R(40, 62, 1, 44, "#8a949c80");
}

function frame(t) {
  if (S && META) { sky(t, S); windsock(t, S); waterSide(t, S); greenhouse(t, S); rain(t, S); }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

cv.addEventListener("click", e => {
  const r = cv.getBoundingClientRect(), y = (e.clientY - r.top) * 200 / r.height;
  const i = BED_Y.findIndex(b => y >= b - 4 && y <= b + 22);
  if (i >= 0) { sel = i; renderZone(); renderSP(); }
});

// ---------------------------------------------------------------- panels
const kv = (l, v, cls = "") => `<div class="${cls}"><span>${l}</span><b>${v}</b></div>`;

function renderTop() {
  const s = S, p = s.plc;
  $("clock").textContent = s.clock; $("day").textContent = `day ${s.day}`;
  $("speedtxt").textContent = s.achieved ? `· ${fx(s.achieved, 0)}× real time` : "";
  $("wxtxt").textContent = `${fx(s.weather.rad, 0)} W/m² · ${fx(s.weather.t_out)} °C · wind ${fx(s.weather.wind)} m/s`;
  document.querySelectorAll("[data-wx]").forEach(b => b.classList.toggle("on", b.dataset.wx === s.weather.look));
  $("plcsub").textContent = `${p.step_name}${p.zone ? " · zone " + p.zone : ""} · ${p.clim}`;
  const ecOk = Math.abs(p.ec - s.sp.SP_EC) <= s.sp.SP_EC_BAND, phOk = Math.abs(p.ph - s.sp.SP_PH) <= s.sp.SP_PH_BAND;
  $("plckv").innerHTML =
    kv("Irrigation", p.manual ? "MANUAL" : p.step_name + (p.enabled ? "" : " (off)")) +
    kv("Radiation sum", `${fx(p.rad_sum, 0)} / ${s.sp.SP_RAD_SUM}`) + kv("Cycles today", p.cycles) +
    kv("EC (set)", `${fx(p.ec, 2)} (${fx(s.sp.SP_EC, 2)})`, p.flow > 50 && !ecOk ? "warn" : "") +
    kv("pH (set)", `${fx(p.ph, 2)} (${fx(s.sp.SP_PH, 2)})`, p.flow > 50 && !phOk ? "warn" : "") +
    kv("Flow", `${fx(p.flow, 0)} L/h`) +
    kv("Air", `${fx(p.t_in)} °C · ${fx(p.rh, 0)} %`) + kv("Climate", p.clim) +
    kv("Vent · fans", `${fx(p.vent, 0)} % · ${p.fan_stage}`) +
    kv("Shade net", p.net) + kv("Tank", `${fx(p.level, 0)} %`) + kv("Water today", `${p.water} L`);
  $("alarms").innerHTML = p.alarms.length ? p.alarms.map(a =>
    `<div><span class="tag ${a.active ? (a.cls === "warning" ? "warn" : "bad") : ""}">${a.tag}</span>${esc(a.text)}${a.active ? "" : " <span class='muted'>(cleared, press Reset)</span>"}</div>`).join("")
    : '<div class="muted">No alarms.</div>';
  $("score").innerHTML = kv("Harvested", `${s.score.kg} kg`) + kv("Harvests", s.score.harvests) + kv("Crops lost", s.score.lost);
  document.querySelectorAll("[data-fault]").forEach(b => { b.classList.toggle("on", s.faults.includes(b.dataset.fault)); b.disabled = s.challenge.active; });
  $("clearf").disabled = s.challenge.active;
}

function cropOptions() {
  return Object.entries(META.crops).map(([k, c]) => `<option value="${k}">${esc(c.name)}</option>`).join("");
}

function renderZone() {
  if (!S) return;
  const z = S.zones[sel];
  $("zonetitle").textContent = `Zone ${sel + 1}${z.crop ? " — " + z.name + " " + z.variant : " — empty"}`;
  $("zonesub").textContent = z.watering ? "watering" : "";
  let h = "";
  if (z.crop) {
    const c = META.crops[z.crop].comfort;
    const stress = Object.keys(z.stress);
    h += `<div class="muted" style="font-size:12px">Stage: <b>${z.stage}</b></div>`;
    h += `<div style="font-size:12px">Growth ${fx(z.maturity, 0)} %</div><div class="meter"><i style="width:${z.maturity}%"></i></div>`;
    h += `<div style="font-size:12px">Health ${fx(z.health, 0)} %</div><div class="meter"><i style="width:${z.health}%;background:${z.health > 60 ? "var(--accent)" : z.health > 30 ? "var(--warn)" : "var(--bad)"}"></i></div>`;
    h += `<div>${stress.length ? stress.map(k => `<span class="tag ${z.stress[k] < 0.3 ? "bad" : "warn"}">${k}</span>`).join("") : '<span class="tag ok">comfortable</span>'}</div>`;
    h += `<div class="muted" style="font-size:12px;margin-top:4px">Likes ${c[1]}–${c[2]} °C, EC ${c[4]}–${c[5]}. Last water: EC ${fx(z.last_ec, 2)}, pH ${fx(z.last_ph, 2)}. Substrate deficit ${fx(z.deficit, 0)} L.</div>`;
    h += `<div class="bar"><button id="harvest" class="primary" ${z.stage === "ripe" ? "" : "disabled"}>Harvest</button><button id="clearbed">Clear bed</button></div>`;
  }
  h += `<div class="bar"><select id="pcrop" aria-label="Crop">${cropOptions()}</select><select id="pvar" aria-label="Variety"></select><button id="plantbtn">${z.crop ? "Replant" : "Plant"}</button></div>`;
  $("zonebody").innerHTML = h;
  const fillVar = () => { $("pvar").innerHTML = META.crops[$("pcrop").value].variants.map((v, i) => `<option value="${i}">${esc(v.name)} · ${v.days} d</option>`).join(""); };
  $("pcrop").onchange = fillVar; fillVar();
  $("plantbtn").onclick = () => send({cmd: "plant", zone: sel, crop: $("pcrop").value, variant: +$("pvar").value});
  if ($("harvest")) $("harvest").onclick = () => send({cmd: "harvest", zone: sel});
  if ($("clearbed")) $("clearbed").onclick = () => send({cmd: "harvest", zone: sel});
}

const SP_SHOW = [["SP_EC", "EC"], ["SP_PH", "pH"], ["SP_VENT_T", "Vent opens above (°C)"], ["SP_COOL_T", "Pad-and-fan above (°C)"],
                 ["SP_RAD_SUM", "Radiation sum to irrigate (J/cm²)"], ["SHOT", "Shot size, this zone (L)"]];
function renderSP() {
  if (!S || !META) return;
  const meta = Object.fromEntries(META.setpoints.map(m => [m.name, m]));
  $("sps").innerHTML = SP_SHOW.map(([n, label]) => {
    const name = n === "SHOT" ? `SP_SHOT_Z${sel + 1}` : n, m = meta[name], v = S.sp[name];
    return `<label>${esc(label)}<b style="text-align:right">${+v.toFixed(2)}</b>
      <input type="range" data-sp="${name}" min="${m.lo}" max="${m.hi}" step="${1 / m.scale}" value="${v}"></label>`;
  }).join("");
  document.querySelectorAll("[data-sp]").forEach(r => {
    r.oninput = () => { dragging = r.dataset.sp; r.previousElementSibling.textContent = +(+r.value).toFixed(2); };
    r.onchange = () => { send({cmd: "setpoint", name: r.dataset.sp, value: +r.value}); dragging = null; };
  });
}
function refreshSP() {
  document.querySelectorAll("[data-sp]").forEach(r => {
    if (dragging === r.dataset.sp) return;
    const v = S.sp[r.dataset.sp]; r.value = v; r.previousElementSibling.textContent = +v.toFixed(2);
  });
}

function renderChallenge() {
  const c = S.challenge, r = S.result;
  let h = "";
  if (!c.active) {
    h = `<div class="muted" style="font-size:12.5px">A hidden fault is injected. Watch the plant and the controller, then name the fault.</div>
         <div class="bar"><button id="cstart" class="primary">Start challenge</button></div>`;
    if (r) h += `<div class="result ${r.correct ? "good" : "badr"}"><b>${r.correct ? "✔ Correct" : "✘ Not quite"}: ${esc(r.title)}</b>
      ${r.correct ? "" : `<div>You answered: ${esc(r.answered)}</div>`}<div class="muted">${r.sim_min} simulated minutes${r.hints ? ", field check used" : ""}</div>
      <dl><dt>Symptoms</dt><dd>${esc(r.symptoms)}</dd><dt>Confirm</dt><dd>${esc(r.checks)}</dd><dt>Cause</dt><dd>${esc(r.cause)}</dd><dt>Fix</dt><dd>${esc(r.fix)}</dd></dl></div>`;
  } else {
    h = `<div class="muted" style="font-size:12.5px">Running for ${c.sim_min} simulated minutes.</div>
      <div class="bar"><button id="chint" ${c.hints ? "disabled" : ""}>Field check (walk the site)</button></div>`;
    if (c.truth) h += `<div class="result" style="font-size:12px">Reference meters: ${fx(c.truth.t_in)} °C, EC ${fx(c.truth.ec, 2)}, pH ${fx(c.truth.ph, 2)}, flow ${fx(c.truth.flow, 0)} L/h, vent ${fx(c.truth.vent, 0)} %
      <div>${Object.entries(c.field).map(([k, ok]) => `<div>${ok ? "✔" : "<b style='color:var(--bad)'>✘</b>"} ${esc(k)}</div>`).join("")}</div></div>`;
    h += `<div class="bar"><select id="cpick" aria-label="Your diagnosis"><option value="">Your diagnosis…</option>${
      META.faults.map(f => `<option value="${f.id}">${esc(f.title)}</option>`).join("")}</select>
      <button id="canswer" class="primary">Submit</button><button id="cquit">Give up</button></div>`;
  }
  if ($("chal").dataset.key !== JSON.stringify([c.active, c.hints, !!r, r && r.title])) {
    $("chal").innerHTML = h;
    $("chal").dataset.key = JSON.stringify([c.active, c.hints, !!r, r && r.title]);
    if ($("cstart")) $("cstart").onclick = () => send({cmd: "challenge", action: "start"});
    if ($("chint")) $("chint").onclick = () => send({cmd: "challenge", action: "hint"});
    if ($("canswer")) $("canswer").onclick = () => $("cpick").value && send({cmd: "challenge", action: "answer", fault: $("cpick").value});
    if ($("cquit")) $("cquit").onclick = () => send({cmd: "challenge", action: "quit"});
  } else if (c.active) {
    const info = $("chal").querySelector(".muted"); if (info) info.textContent = `Running for ${c.sim_min} simulated minutes.`;
  }
}

function buildStatic() {
  $("speeds").innerHTML = [[0, "Pause"], [1, "1×"], [5, "5×"], [20, "20×"], ["max", "Max"]]
    .map(([v, l]) => `<button data-speed="${v}">${l}</button>`).join(" ");
  document.querySelectorAll("[data-speed]").forEach(b => b.onclick = () => {
    speed = b.dataset.speed === "max" ? "max" : +b.dataset.speed;
    send({cmd: "speed", value: speed}); markSpeed();
  });
  markSpeed();
  $("weather").innerHTML = META.scenarios.map(w => `<button data-wx="${w}">${w}</button>`).join(" ");
  document.querySelectorAll("[data-wx]").forEach(b => b.onclick = () => send({cmd: "weather", scenario: b.dataset.wx}));
  $("faults").innerHTML = META.faults.map(f => `<button data-fault="${f.id}" title="${f.level === 3 ? "no alarm: find it from the symptoms" : ""}">${esc(f.title)}${f.level === 3 ? " ·" : ""}</button>`).join("");
  document.querySelectorAll("[data-fault]").forEach(b => b.onclick = () => send({cmd: "fault", name: b.dataset.fault, on: !S.faults.includes(b.dataset.fault)}));
  document.querySelectorAll("[data-hmi]").forEach(b => b.onclick = () => send({cmd: "hmi", name: b.dataset.hmi}));
  $("skip").onclick = () => send({cmd: "skip_night"});
  $("recipe").onclick = () => send({cmd: "recipe"});
  $("clearf").onclick = () => send({cmd: "clear_faults"});
}
function markSpeed() { document.querySelectorAll("[data-speed]").forEach(b => b.classList.toggle("on", String(speed) === b.dataset.speed)); }

let lastZoneKey = "";
worker.onmessage = e => {
  const m = e.data;
  if (m.status) $("loadmsg").textContent = m.status;
  if (m.error) $("loadmsg").textContent = "Could not start: " + m.error;
  if (m.meta) { META = m.meta; buildStatic(); }
  if (m.state) {
    const first = !S; S = m.state;
    if (first) { $("loading").hidden = true; renderZone(); renderSP(); }
    renderTop(); refreshSP(); renderChallenge();
    const z = S.zones[sel], key = [sel, z.crop, z.variant, z.stage, Math.round(z.maturity), Math.round(z.health), Object.keys(z.stress).join(), z.watering].join();
    if (key !== lastZoneKey && !document.activeElement?.closest?.("#zonebody")) { lastZoneKey = key; renderZone(); }
  }
  if (m.reply && !m.reply.ok) console.warn(m.reply.error);
};
