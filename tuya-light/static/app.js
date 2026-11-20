/* Lumora front-end */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (path, body, method) => {
  const res = await fetch(path, {
    method: method || (body !== undefined ? "POST" : "GET"),
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
};
const toast = (msg) => {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2600);
};
const throttle = (fn, ms) => {
  let last = 0, timer = null, args;
  return (...a) => {
    args = a; const now = Date.now(); clearTimeout(timer);
    if (now - last >= ms) { last = now; fn(...args); }
    else timer = setTimeout(() => { last = Date.now(); fn(...args); }, ms - (now - last));
  };
};

// ---------- colour helpers
const hsv2rgb = (h, s, v) => {
  const i = Math.floor(h * 6), f = h * 6 - i, p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  const [r, g, b] = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][((i % 6) + 6) % 6];
  return [r * 255, g * 255, b * 255];
};
const rgb2hsv = (r, g, b) => {
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let h = 0;
  if (d) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [((h / 6) + 1) % 1, mx ? d / mx : 0, mx];
};
const toHex = (rgb) => "#" + rgb.map((c) => Math.round(Math.max(0, Math.min(255, c))).toString(16).padStart(2, "0")).join("");
const fromHex = (h) => { h = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)); };

// ---------- state
let S = {};
let effectsMeta = [];
let palette = ["#ff6a00", "#ee0979", "#7b2ff7", "#00c6ff"];
let currentHS = { h: 0.92, s: 0.8 };
let dragging = false;

// ---------- live state stream
function applyState(st) {
  S = st;
  const rgb = st.preview || [255, 255, 255];
  // Accent = full-brightness version of the colour (keeps buttons readable);
  // the bulb alone shows how bright the light really is.
  const mx = Math.max(...rgb);
  if (mx > 6) applyState.accent = rgb.map((c) => Math.round((c * 255) / mx));
  const accent = applyState.accent || [255, 60, 170];
  document.documentElement.style.setProperty("--glow", `rgb(${accent.join(",")})`);
  $("#bulb").style.filter = `brightness(${(0.25 + 0.75 * mx / 255).toFixed(2)})`;
  document.body.classList.toggle("off", !st.on);
  const pill = $("#status");
  if (st.demo) { pill.textContent = "Demo mode"; pill.className = "pill demo"; }
  else if (st.connected && !st.error) { pill.textContent = "● Connected"; pill.className = "pill ok"; }
  else { pill.textContent = "Offline"; pill.className = "pill err"; pill.title = st.error || ""; }
  const fx = st.effect && effectsMeta.find((e) => e.id === st.effect.id);
  $("#modeLabel").textContent = !st.on ? "Off" :
    st.mode === "white" ? (st.circadian ? "Circadian white" : "White light") :
    st.mode === "effect" && fx ? `${fx.icon} ${fx.label}` :
    st.mode === "live" ? "🎵 Music sync" :
    st.mode === "scene" ? "💎 Bulb scene" : "Colour";
  if (!dragging) {
    const b = Math.round(st.mode === "effect" && st.effect ? st.effect.brightness : st.brightness);
    $("#brightness").value = b; $("#brightnessOut").textContent = b + "%";
    if (st.mode === "colour") { currentHS = { h: st.h, s: st.s }; placeKnob(); }
    if (st.mode === "white") $("#temp").value = st.temp;
    $("#circadian").checked = !!st.circadian;
  }
  $$(".fx").forEach((el) => el.classList.toggle("on", st.mode === "effect" && st.effect && st.effect.id === el.dataset.id));
  $("#effectControls").hidden = !(st.mode === "effect" && st.effect);
  if (st.mode === "effect" && st.effect && fx) {
    $("#effectName").textContent = `${fx.icon} ${fx.label}`;
    $("#paletteBox").hidden = !fx.colors;
  }
  const sl = st.sleep;
  $("#sleepInfo").textContent = sl ? `Fading off in ${Math.floor(sl.remaining / 60)}m ${sl.remaining % 60}s` : "";
}

function connectStream() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => applyState(JSON.parse(e.data));
  es.onerror = () => { es.close(); $("#status").textContent = "Reconnecting…"; setTimeout(connectStream, 2000); };
}

// ---------- tabs
$$("#tabs button").forEach((b) => b.addEventListener("click", () => {
  $$("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  $$(".panel").forEach((p) => (p.hidden = p.dataset.tab !== b.dataset.tab));
  try { localStorage.setItem("lumora.tab", b.dataset.tab); } catch {}
}));
try { const t = localStorage.getItem("lumora.tab"); if (t) $(`#tabs button[data-tab="${t}"]`)?.click(); } catch {}

// ---------- power & brightness
const togglePower = () => api("/api/power", { on: !S.on }).then(applyState).catch((e) => toast(e.message));
$("#bulb").onclick = togglePower;
$("#powerBtn").onclick = togglePower;
const sendBrightness = throttle((v) => api("/api/brightness", { value: v }).catch(() => {}), 150);
$("#brightness").addEventListener("input", (e) => {
  dragging = true; clearTimeout(sendBrightness.t);
  $("#brightnessOut").textContent = e.target.value + "%";
  sendBrightness(+e.target.value);
  sendBrightness.t = setTimeout(() => (dragging = false), 600);
});

// ---------- colour wheel
const wheel = $("#wheel"), wctx = wheel.getContext("2d");
(function drawWheel() {
  const { width: w } = wheel, r = w / 2, img = wctx.createImageData(w, w);
  for (let y = 0; y < w; y++) for (let x = 0; x < w; x++) {
    const dx = x - r, dy = y - r, d = Math.sqrt(dx * dx + dy * dy);
    if (d > r) continue;
    const h = (Math.atan2(dy, dx) / (2 * Math.PI) + 1) % 1, [R, G, B] = hsv2rgb(h, d / r, 1);
    const i = (y * w + x) * 4; img.data[i] = R; img.data[i + 1] = G; img.data[i + 2] = B; img.data[i + 3] = 255;
  }
  wctx.putImageData(img, 0, 0);
})();
function placeKnob() {
  const k = $("#wheelKnob"), a = currentHS.h * 2 * Math.PI, rr = currentHS.s * 50;
  k.style.left = 50 + Math.cos(a) * rr + "%"; k.style.top = 50 + Math.sin(a) * rr + "%";
  k.style.background = toHex(hsv2rgb(currentHS.h, currentHS.s, 1));
  const hex = toHex(hsv2rgb(currentHS.h, currentHS.s, 1));
  if (document.activeElement !== $("#hexInput")) $("#hexInput").value = hex;
  $("#nativeColour").value = hex;
  renderHarmonies();
}
const sendColour = throttle(() => api("/api/colour", { h: currentHS.h, s: currentHS.s, brightness: +$("#brightness").value }).catch((e) => toast(e.message)), 120);
function wheelPick(e) {
  const rect = wheel.getBoundingClientRect(), r = rect.width / 2;
  const dx = e.clientX - rect.left - r, dy = e.clientY - rect.top - r;
  currentHS = { h: (Math.atan2(dy, dx) / (2 * Math.PI) + 1) % 1, s: Math.min(1, Math.hypot(dx, dy) / r) };
  placeKnob(); sendColour();
}
wheel.addEventListener("pointerdown", (e) => { dragging = true; wheel.setPointerCapture(e.pointerId); wheelPick(e); });
wheel.addEventListener("pointermove", (e) => { if (dragging && e.buttons) wheelPick(e); });
wheel.addEventListener("pointerup", () => setTimeout(() => (dragging = false), 400));
function setHex(hex) {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return;
  const [h, s] = rgb2hsv(...fromHex(hex)); currentHS = { h, s }; placeKnob(); sendColour();
}
$("#hexInput").addEventListener("change", (e) => setHex(e.target.value.startsWith("#") ? e.target.value : "#" + e.target.value));
$("#nativeColour").addEventListener("input", (e) => setHex(e.target.value));
["#ff0000", "#ff7a00", "#ffd000", "#3dff6e", "#00e5ff", "#2962ff", "#8e24ff", "#ff2bd6", "#ff3c6f", "#ffffff"].forEach((c) => {
  const b = document.createElement("button"); b.className = "swatch"; b.style.background = c; b.title = c;
  b.onclick = () => setHex(c); $("#swatches").append(b);
});

function renderHarmonies() {
  const { h, s } = currentHS, sat = Math.max(0.65, s);
  const mk = (offs) => offs.map((o) => toHex(hsv2rgb((h + o + 1) % 1, sat, 1)));
  const sets = [
    ["Complementary", mk([0, 0.5])], ["Triadic", mk([0, 1 / 3, 2 / 3])],
    ["Analogous", mk([-1 / 12, 0, 1 / 12])], ["Split", mk([0, 5 / 12, 7 / 12])],
  ];
  const box = $("#harmonies"); box.innerHTML = "";
  sets.forEach(([name, cols]) => {
    const b = document.createElement("button"); b.className = "harmony";
    b.innerHTML = `<div class="bar">${cols.map((c) => `<i style="background:${c}"></i>`).join("")}</div><span>${name}</span>`;
    b.onclick = () => { palette = cols; startEffect("gradient"); renderPalette(); };
    box.append(b);
  });
}

// ---------- white
const whitePresets = [["Candle", 0, 35, "#ffb066"], ["Relax", 20, 60, "#ffd29c"], ["Read", 55, 90, "#fff1dc"], ["Focus", 100, 100, "#dde9ff"]];
whitePresets.forEach(([name, temp, bri, col]) => {
  const b = document.createElement("button"); b.className = "wp"; b.style.background = col; b.textContent = name;
  b.onclick = () => api("/api/white", { temp, brightness: bri }).then(applyState);
  $("#whitePresets").append(b);
});
const sendWhite = throttle(() => api("/api/white", { temp: +$("#temp").value, brightness: +$("#brightness").value }), 150);
$("#temp").addEventListener("input", () => { dragging = true; sendWhite(); clearTimeout(sendWhite.t); sendWhite.t = setTimeout(() => (dragging = false), 600); });
$("#circadian").addEventListener("change", (e) => api("/api/white", { circadian: e.target.checked, temp: +$("#temp").value }).then(applyState));

// ---------- effects
const fxBg = {
  gradient: "linear-gradient(120deg,#ff6a00,#ee0979,#7b2ff7,#00c6ff)", breathe: "radial-gradient(#ff3cac,#2b1640)",
  rainbow: "linear-gradient(90deg,red,orange,yellow,lime,cyan,blue,magenta,red)", aurora: "linear-gradient(160deg,#00ffa3,#00b3ff,#7a00ff,#00ff6a)",
  candle: "radial-gradient(circle at 50% 70%,#ffc46b,#ff6a00 40%,#3a1300)", fireplace: "linear-gradient(0deg,#ff2a00,#ff9a1f,#3a0a00)",
  ocean: "linear-gradient(180deg,#00d2d3,#0047ab,#001a4d)", lava: "linear-gradient(140deg,#ff0080,#ff4d00,#ffb300,#c400ff)",
  galaxy: "radial-gradient(circle at 30% 30%,#ff00cc,#3333ff 40%,#120024)", sunset: "linear-gradient(180deg,#ffd56b,#ff8c42,#ff3c38,#a23b72,#2e1f6b)",
  storm: "linear-gradient(180deg,#0a0e3c,#2a3070,#e6e6ff 52%,#0a0e3c 55%)", heartbeat: "radial-gradient(#ff1744,#3a0010)",
  party: "conic-gradient(#ff0040,#ffe600,#00ff9d,#0080ff,#c800ff,#ff0040)", police: "linear-gradient(90deg,#ff0000 50%,#0028ff 50%)",
  strobe: "repeating-linear-gradient(90deg,#fff 0 12px,#111 12px 24px)", sunrise: "linear-gradient(0deg,#280000,#b41e00,#ff7814,#ffebc8)",
};
const ideas = {
  Synthwave: ["#ff2a6d", "#d300c5", "#7a04eb", "#05d9e8"], Forest: ["#0b6e4f", "#73a942", "#d8f3dc", "#2d6a4f"],
  "Cotton candy": ["#ffafcc", "#cdb4db", "#a2d2ff", "#bde0fe"], Cyberpunk: ["#fcee0a", "#ff003c", "#00f0ff"],
  Tropical: ["#ff9f1c", "#ffbf69", "#2ec4b6", "#00b4d8"], Ember: ["#ff4800", "#ff9e00", "#9d0208"],
};
function renderEffects() {
  const g = $("#effectGrid"); g.innerHTML = "";
  effectsMeta.forEach((e) => {
    const b = document.createElement("button"); b.className = "fx"; b.dataset.id = e.id;
    b.innerHTML = `<span class="bg" style="background-image:${fxBg[e.id] || "#333"}"></span><span class="ico">${e.icon}</span><span class="lbl">${e.label}</span>`;
    b.onclick = () => startEffect(e.id);
    g.append(b);
  });
  const ib = $("#paletteIdeas"); ib.innerHTML = "";
  Object.entries(ideas).forEach(([name, cols]) => {
    const b = document.createElement("button"); b.className = "chip idea";
    b.innerHTML = `<i style="background:linear-gradient(90deg,${cols.join(",")})"></i>${name}`;
    b.onclick = () => { palette = [...cols]; renderPalette(); pushPalette(); };
    ib.append(b);
  });
}
function startEffect(id) {
  const meta = effectsMeta.find((e) => e.id === id);
  api("/api/effect", { id, speed: +$("#speed").value / 100, colors: meta && meta.colors ? palette : [], brightness: +$("#brightness").value })
    .then(applyState).catch((e) => toast(e.message));
}
const pushPalette = throttle(() => api("/api/effect", { colors: palette }).catch(() => {}), 200);
function renderPalette() {
  const box = $("#paletteEditor"); box.innerHTML = "";
  palette.forEach((c, i) => {
    const d = document.createElement("div"); d.className = "pe";
    d.innerHTML = `<input type="color" value="${c}" aria-label="Palette colour ${i + 1}"><button aria-label="Remove">×</button>`;
    $("input", d).oninput = (e) => { palette[i] = e.target.value; pushPalette(); };
    $("button", d).onclick = () => { if (palette.length > 1) { palette.splice(i, 1); renderPalette(); pushPalette(); } };
    box.append(d);
  });
  $("#scenePalette").style.background = `linear-gradient(90deg,${palette.length > 1 ? palette.join(",") : palette[0] + "," + palette[0]})`;
  try { localStorage.setItem("lumora.palette", JSON.stringify(palette)); } catch {}
}
try { const p = JSON.parse(localStorage.getItem("lumora.palette")); if (Array.isArray(p) && p.length) palette = p; } catch {}
$("#addColour").onclick = () => { if (palette.length < 8) { palette.push(toHex(hsv2rgb(Math.random(), 0.9, 1))); renderPalette(); pushPalette(); } };
$("#speed").addEventListener("input", throttle((e) => {
  const v = +$("#speed").value / 100; $("#speedOut").textContent = v.toFixed(1) + "×";
  api("/api/effect", { speed: v }).catch(() => {});
}, 150));
$("#effectStop").onclick = () => api("/api/colour", { h: currentHS.h, s: currentHS.s, brightness: +$("#brightness").value }).then(applyState);

// ---------- native bulb scene
let sceneMode = "gradient";
$$("#sceneMode button").forEach((b) => b.onclick = () => {
  sceneMode = b.dataset.v; $$("#sceneMode button").forEach((x) => x.classList.toggle("on", x === b));
});
$("#sceneSpeed").oninput = (e) => ($("#sceneSpeedOut").textContent = e.target.value);
$("#sceneSend").onclick = () => api("/api/scene", { colors: palette, mode: sceneMode, speed: +$("#sceneSpeed").value })
  .then((st) => { applyState(st); toast("Saved into the bulb 💎"); }).catch((e) => toast(e.message));

// ---------- shake for a surprise colour
let shakeOn = false, lastShake = 0;
function onMotion(e) {
  const a = e.accelerationIncludingGravity || e.acceleration; if (!a) return;
  const force = Math.abs(a.x || 0) + Math.abs(a.y || 0) + Math.abs(a.z || 0);
  if (force > 32 && Date.now() - lastShake > 900) {
    lastShake = Date.now();
    currentHS = { h: Math.random(), s: 0.75 + Math.random() * 0.25 }; placeKnob(); sendColour();
    if (navigator.vibrate) navigator.vibrate(30);
  }
}
$("#shakeBtn").onclick = async () => {
  if (!shakeOn && typeof DeviceMotionEvent !== "undefined" && DeviceMotionEvent.requestPermission) {
    try { if ((await DeviceMotionEvent.requestPermission()) !== "granted") { toast("Motion access was denied"); return; } }
    catch { toast("Motion needs https"); return; }
  }
  shakeOn = !shakeOn;
  if (shakeOn) window.addEventListener("devicemotion", onMotion);
  else window.removeEventListener("devicemotion", onMotion);
  $("#shakeBtn").textContent = `📳 Shake phone for a surprise colour: ${shakeOn ? "ON" : "off"}`;
};

// ---------- music sync
let audio = null;
let musicStyle = "spectrum";
$$("#musicStyle button").forEach((b) => b.onclick = () => {
  musicStyle = b.dataset.v; $$("#musicStyle button").forEach((x) => x.classList.toggle("on", x === b));
});
$("#gain").oninput = (e) => ($("#gainOut").textContent = (e.target.value / 100).toFixed(1) + "×");
$("#micBtn").onclick = async () => {
  if (audio) { stopMusic(); return; }
  if (!navigator.mediaDevices?.getUserMedia) { toast("Microphone needs https or localhost on this device"); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    const ctx = new AudioContext(), src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser();
    an.fftSize = 1024; an.smoothingTimeConstant = 0.6; src.connect(an);
    if (ctx.state === "suspended") await ctx.resume();
    let wake = null; try { wake = await navigator.wakeLock?.request("screen"); } catch {}
    audio = { wake, ctx, stream, an, buf: new Uint8Array(an.frequencyBinCount), hue: Math.random(), avg: 0, lastSend: 0, beatHue: 0, level: 0 };
    $("#micBtn").textContent = "⏹ Stop music sync";
    musicLoop();
  } catch (e) { toast("Mic blocked: " + e.message); }
};
function stopMusic() {
  audio.stream.getTracks().forEach((t) => t.stop()); audio.ctx.close();
  try { audio.wake?.release(); } catch {}
  audio = null;
  $("#micBtn").textContent = "🎤 Start music sync";
}
function musicLoop() {
  if (!audio) return;
  requestAnimationFrame(musicLoop);
  const { an, buf } = audio, gain = +$("#gain").value / 100;
  an.getByteFrequencyData(buf);
  const n = buf.length, bassEnd = Math.floor(n * 0.04);
  let sum = 0, bass = 0, wsum = 0, wtot = 0;
  for (let i = 0; i < n; i++) { const v = buf[i] / 255; sum += v; if (i < bassEnd) bass += v; wsum += v * i; wtot += v; }
  const level = Math.min(1, (sum / n) * 3.2 * gain), bassL = Math.min(1, (bass / bassEnd) * gain);
  const centroid = wtot ? wsum / wtot / n : 0;
  audio.avg = audio.avg * 0.95 + bassL * 0.05;
  const beat = bassL > audio.avg * 1.35 && bassL > 0.3;
  audio.level = Math.max(level, audio.level * 0.85);
  let rgb;
  if (musicStyle === "spectrum") {
    audio.hue = audio.hue * 0.9 + (centroid * 3 % 1) * 0.1;
    rgb = hsv2rgb(audio.hue, 1, 0.08 + 0.92 * audio.level);
  } else if (musicStyle === "pulse") {
    const [r, g, b] = hsv2rgb(currentHS.h, currentHS.s, 1);
    rgb = [r, g, b].map((c) => c * (0.05 + 0.95 * audio.level));
  } else {
    if (beat && performance.now() - (audio.lastBeat || 0) > 180) { audio.lastBeat = performance.now(); audio.beatIdx = ((audio.beatIdx || 0) + 1) % palette.length; }
    const [r, g, b] = fromHex(palette[audio.beatIdx || 0]);
    const since = (performance.now() - (audio.lastBeat || 0)) / 400;
    rgb = [r, g, b].map((c) => c * Math.max(0.1, 1 - since));
  }
  drawViz(buf, rgb);
  const now = performance.now();
  if (now - audio.lastSend > 80) { audio.lastSend = now; api("/api/live", { r: rgb[0], g: rgb[1], b: rgb[2], smooth: $("#smoothMusic").checked && musicStyle !== "beat" }).catch(() => {}); }
}
function drawViz(buf, rgb) {
  const c = $("#viz"), x = c.getContext("2d"), w = c.width, h = c.height, bars = 48;
  x.clearRect(0, 0, w, h); x.fillStyle = toHex(rgb.map((v) => Math.max(v, 40)));
  for (let i = 0; i < bars; i++) {
    const v = buf[Math.floor(Math.pow(i / bars, 1.8) * buf.length * 0.7)] / 255, bh = v * h;
    x.fillRect(i * (w / bars) + 2, h - bh, w / bars - 4, bh);
  }
}

// ---------- photo mood
let photoCols = [];
$("#photoInput").onchange = (e) => {
  const f = e.target.files[0]; if (!f) return;
  const img = new Image();
  img.onload = () => {
    const c = $("#photoCanvas"), ctx = c.getContext("2d"), max = 720, k = Math.min(1, max / Math.max(img.width, img.height));
    c.width = img.width * k; c.height = img.height * k; ctx.drawImage(img, 0, 0, c.width, c.height); c.hidden = false;
    photoCols = extractPalette(ctx.getImageData(0, 0, c.width, c.height).data, 5);
    const box = $("#photoPalette"); box.innerHTML = "";
    photoCols.forEach((col) => { const b = document.createElement("button"); b.className = "swatch"; b.style.background = col; b.onclick = () => setHex(col); box.append(b); });
    $("#photoPlay").hidden = false;
    URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(f);
};
$("#photoCanvas").addEventListener("click", (e) => {
  const c = e.target, r = c.getBoundingClientRect();
  const px = c.getContext("2d").getImageData((e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height, 1, 1).data;
  setHex(toHex([px[0], px[1], px[2]])); toast("Colour grabbed");
});
$("#photoPlay").onclick = () => { palette = [...photoCols]; renderPalette(); startEffect("gradient"); toast("Playing your photo's mood"); };
function extractPalette(data, k) {
  // k-means on vivid-ish pixels; light bulbs look best with saturated colours
  const px = [];
  for (let i = 0; i < data.length; i += 4 * 7) {
    const [h, s, v] = rgb2hsv(data[i], data[i + 1], data[i + 2]);
    if (v > 0.2 && s > 0.15) px.push([data[i], data[i + 1], data[i + 2]]);
  }
  if (px.length < k) return ["#ff3cac", "#784ba0", "#2b86c5"];
  let cents = Array.from({ length: k }, (_, i) => px[Math.floor((i + 0.5) * px.length / k)].slice());
  for (let it = 0; it < 10; it++) {
    const acc = cents.map(() => [0, 0, 0, 0]);
    for (const p of px) {
      let bi = 0, bd = 1e9;
      cents.forEach((c, j) => { const d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2; if (d < bd) { bd = d; bi = j; } });
      const a = acc[bi]; a[0] += p[0]; a[1] += p[1]; a[2] += p[2]; a[3]++;
    }
    cents = acc.map((a, j) => (a[3] ? [a[0] / a[3], a[1] / a[3], a[2] / a[3]] : cents[j]));
  }
  // boost saturation so the bulb shows a rich version of each colour
  return cents.map((c) => { const [h, s] = rgb2hsv(...c); return toHex(hsv2rgb(h, Math.min(1, s * 1.35 + 0.1), 1)); });
}

// ---------- timers
[["15 min", 15], ["30 min", 30], ["1 hour", 60], ["Cancel", 0]].forEach(([l, m]) => {
  const b = document.createElement("button"); b.className = "chip"; b.textContent = l;
  b.onclick = () => api("/api/sleep", { minutes: m }).then((s) => { applyState(s); toast(m ? `Sleep fade: ${l}` : "Sleep timer cancelled"); });
  $("#sleepBtns").append(b);
});
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const alarmDays = new Set([0, 1, 2, 3, 4]);
DAYS.forEach((d, i) => {
  const b = document.createElement("button"); b.textContent = d; b.classList.toggle("on", alarmDays.has(i));
  b.onclick = () => { alarmDays.has(i) ? alarmDays.delete(i) : alarmDays.add(i); b.classList.toggle("on"); };
  $("#alarmDays").append(b);
});
$("#alarmAdd").onclick = () => api("/api/alarms", { time: $("#alarmTime").value, duration: +$("#alarmDur").value, days: [...alarmDays].sort() })
  .then(() => { loadAlarms(); toast("Sunrise alarm set"); }).catch((e) => toast(e.message));
async function loadAlarms() {
  const list = await api("/api/alarms"), box = $("#alarmList"); box.innerHTML = "";
  list.sort((a, b) => a.time.localeCompare(b.time)).forEach((a) => {
    const d = document.createElement("div"); d.className = "card alarm";
    d.innerHTML = `<div><b>${a.time}</b><div class="hint">${a.duration} min sunrise · ${a.days.length === 7 ? "Every day" : a.days.map((i) => DAYS[i]).join(" ")}</div></div>
      <div class="row gap"><input type="checkbox" ${a.enabled ? "checked" : ""} aria-label="Enabled"><button class="chip">Delete</button></div>`;
    $("input", d).onchange = (e) => api("/api/alarms", { ...a, enabled: e.target.checked });
    $("button", d).onclick = () => api(`/api/alarms/${a.id}`, undefined, "DELETE").then(loadAlarms);
    box.append(d);
  });
}

// ---------- presets
async function loadPresets() {
  const list = await api("/api/presets"), box = $("#presets"); box.innerHTML = "";
  list.forEach((p) => {
    const b = document.createElement("button"); b.className = "preset";
    const col = p.state.preview ? `rgb(${p.state.preview.join(",")})` : "#888";
    const bg = p.state.mode === "effect" && p.state.effect?.colors?.length ? `linear-gradient(135deg,${p.state.effect.colors.join(",")})` : col;
    b.innerHTML = `<i style="background:${bg}"></i>${p.name.replace(/[<>&]/g, "")}<span class="x" title="Delete">✕</span>`;
    b.onclick = (e) => {
      if (e.target.classList.contains("x")) { api(`/api/presets/${p.id}`, undefined, "DELETE").then(loadPresets); return; }
      if (p.state.effect?.colors?.length) { palette = [...p.state.effect.colors]; renderPalette(); }
      api(`/api/presets/${p.id}/apply`, {}).then(applyState);
    };
    box.append(b);
  });
}
$("#savePreset").onclick = async () => {
  const name = prompt("Name this look", S.mode === "effect" ? "My vibe" : "My colour");
  if (!name) return;
  await api("/api/presets", { name }); loadPresets(); toast("Saved ✓");
};

// ---------- setup
try { $("#cloudRegion").value = localStorage.getItem("lumora.region") || "in"; } catch {}
$("#cloudFetch").onclick = async () => {
  $("#cloudMsg").textContent = "Asking Tuya for your devices…";
  try { localStorage.setItem("lumora.region", $("#cloudRegion").value); } catch {}
  try {
    const list = await api("/api/cloud-devices", { region: $("#cloudRegion").value, apiKey: $("#cloudKey").value, apiSecret: $("#cloudSecret").value });
    $("#cloudMsg").textContent = list.length ? `✅ Found ${list.length} device(s). Tap your bulb below, then Connect.` : "No devices found. Did you link your Smart Life app to the project?";
    loadConfig();
  } catch (e) { $("#cloudMsg").textContent = "❌ " + e.message; }
};
async function loadConfig() {
  const c = await api("/api/config"), d = c.device || {};
  $("#cfgId").value = d.id || ""; $("#cfgKey").value = d.key || ""; $("#cfgIp").value = d.ip || "";
  $("#cfgVer").value = d.version || "3.3"; $("#cfgFps").value = c.fps; $("#fpsOut").textContent = c.fps;
  $("#lanHint").textContent = `Open http://${c.lan}:${location.port || 80} on your phone (same WiFi) to control from there. Tip: "Add to Home Screen" makes it feel like an app.`;
  if (!c.tinytuya) $("#cfgMsg").textContent = "⚠ tinytuya is not installed — run: pip install -r requirements.txt";
  const wiz = await api("/api/wizard-devices").catch(() => []);
  const wl = $("#wizardList"); wl.innerHTML = "";
  if (wiz.length) {
    wl.innerHTML = `<div class="hint">Found in devices.json — tap to fill in:</div>`;
    wiz.forEach((w) => {
      const b = document.createElement("button"); b.className = "list-item chip"; b.style.width = "100%";
      b.textContent = `${w.name || "Device"} · ${w.id}`;
      b.onclick = () => { $("#cfgId").value = w.id; $("#cfgKey").value = w.key; $("#cfgIp").value = w.ip || ""; $("#cfgVer").value = String(w.version || "3.3"); };
      wl.append(b);
    });
  }
}
$("#cfgFps").oninput = (e) => ($("#fpsOut").textContent = e.target.value);
$("#cfgSave").onclick = async () => {
  $("#cfgMsg").textContent = "Connecting…";
  try {
    const st = await api("/api/config", { device: { id: $("#cfgId").value, key: $("#cfgKey").value, ip: $("#cfgIp").value, version: $("#cfgVer").value }, fps: +$("#cfgFps").value });
    applyState(st);
    $("#cfgMsg").textContent = st.connected ? "✅ Connected to your bulb!" : `❌ Couldn't connect: ${st.error || "unknown error"}. Check key, IP and version.`;
    loadConfig();
  } catch (e) { $("#cfgMsg").textContent = "❌ " + e.message; }
};
$("#cfgForget").onclick = () => api("/api/config", undefined, "DELETE").then(() => { loadConfig(); toast("Back to demo mode"); });
$("#cfgScan").onclick = async () => {
  const box = $("#scanList"); box.innerHTML = `<div class="hint">Scanning your WiFi for Tuya devices (~20s)…</div>`;
  try {
    const list = await api("/api/scan");
    box.innerHTML = list.length ? "" : `<div class="hint">No devices found. Is this computer on the same WiFi as the bulb?</div>`;
    list.forEach((d) => {
      const b = document.createElement("button"); b.className = "list-item chip"; b.style.width = "100%";
      b.textContent = `${d.ip} · ${d.id} · v${d.version}`;
      b.onclick = () => { $("#cfgIp").value = d.ip; if (!$("#cfgId").value) $("#cfgId").value = d.id; $("#cfgVer").value = String(d.version); };
      box.append(b);
    });
  } catch (e) { box.innerHTML = `<div class="hint">Scan failed: ${e.message}</div>`; }
};

// ---------- boot
(async () => {
  effectsMeta = await api("/api/effects");
  renderEffects(); renderPalette(); placeKnob();
  applyState(await api("/api/state"));
  connectStream(); loadPresets(); loadAlarms(); loadConfig();
})();
