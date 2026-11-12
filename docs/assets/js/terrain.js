/* ------------------------------------------------------------------
   Stylised Auckland volcanic field.
   One height function drives both the 3D hero map and every 2D
   contour panel on the page, so all the "maps" agree with each other.

   Map units: x in [-1, 1] runs west -> east, z in [-1, 1] runs
   north -> south. Heights are in metres.
   ------------------------------------------------------------------ */

const smoothstep = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/* Approximate bounding box used to turn map units into coordinates. */
const LAT0 = -36.85;
const LON0 = 174.77;
const SPAN = 0.11;

/* Sea-level line of the Waitematā shore (z of the coast for a given x). */
export const coastZ = (x) =>
  -0.2 + 0.06 * Math.sin(x * 4.2 + 0.8) + 0.035 * Math.sin(x * 10.5 + 2.0);

/* Positive on land, negative at sea. */
export const coastDist = (x, z) => z - coastZ(x);

function rolling(x, z) {
  return (
    0.5 +
    0.22 * Math.sin(x * 6.3 + z * 2.1) +
    0.16 * Math.sin(-x * 3.7 + z * 7.9 + 1.3) +
    0.09 * Math.sin(x * 12.1 - z * 10.3 + 0.4)
  );
}

function baseAt(x, z) {
  const d = coastDist(x, z);
  const land = smoothstep(-0.04, 0.1, d);
  const ground = 6 + 48 * rolling(x, z) * smoothstep(-0.02, 0.45, d);
  return land * ground + (1 - land) * -18;
}

/* Cone profile: a broad cone with a crater bowl at the top. q = (r / R)^2 */
const profile = (q, crater) => Math.exp(-q * 2.2) - crater * Math.exp(-q * 20);

function profilePeak(crater) {
  let peak = 0;
  for (let q = 0; q <= 0.6; q += 0.002) peak = Math.max(peak, profile(q, crater));
  return peak;
}

/* Real summit heights, positions stylised. */
const RAW_CONES = [
  { name: 'Rangitoto', x: 0.5, z: -0.6, h: 260, r: 0.34, crater: 0.04 },
  { name: 'Maungawhau', x: -0.12, z: 0.06, h: 196, r: 0.12, crater: 0.32 },
  { name: 'Maungakiekie', x: 0.16, z: 0.42, h: 182, r: 0.14, crater: 0.2 },
  { name: 'Ōwairaka', x: -0.52, z: 0.22, h: 135, r: 0.11, crater: 0.22 },
  { name: 'Maungarei', x: 0.6, z: 0.3, h: 135, r: 0.11, crater: 0.28 },
  { name: 'Te Kōpuke', x: 0.07, z: 0.11, h: 126, r: 0.08, crater: 0.3 },
  { name: 'Puketāpapa', x: -0.32, z: 0.55, h: 110, r: 0.09, crater: 0.2 },
  { name: 'Takarunga', x: 0.08, z: -0.43, h: 87, r: 0.07, crater: 0.16 },
  { name: 'Maungauika', x: 0.24, z: -0.47, h: 50, r: 0.06, crater: 0.16 },
];

export const CONES = RAW_CONES.map((c) => ({
  ...c,
  amp: (c.h - baseAt(c.x, c.z)) / profilePeak(c.crater),
}));

export function heightAt(x, z) {
  let h = baseAt(x, z);
  for (let i = 0; i < CONES.length; i++) {
    const c = CONES[i];
    const dx = x - c.x;
    const dz = z - c.z;
    const q = (dx * dx + dz * dz) / (c.r * c.r);
    if (q < 9) h += c.amp * profile(q, c.crater);
  }
  return h;
}

/* The career route, from "Now" in the south to "Vision" on Rangitoto. */
export const ROUTE = [
  [0.34, 0.68], [0.27, 0.56], [0.16, 0.42],
  [0.07, 0.3], [-0.05, 0.17], [-0.12, 0.06],
  [-0.07, -0.1], [0.05, -0.25], [0.21, -0.39], [0.37, -0.52], [0.5, -0.6],
];

export const WAYPOINTS = [
  { n: '01', label: 'Now', place: 'Auckland', x: 0.34, z: 0.68 },
  { n: '02', label: 'Graduate', place: 'Maungakiekie 182 m', x: 0.16, z: 0.42 },
  { n: '03', label: 'Next role', place: 'Maungawhau 196 m', x: -0.12, z: 0.06 },
  { n: '04', label: 'Vision', place: 'Rangitoto 260 m', x: 0.5, z: -0.6 },
];

export function toLatLon(x, z) {
  return { lat: LAT0 - z * SPAN, lon: LON0 + x * SPAN };
}

export function formatLatLon({ lat, lon }) {
  return `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}  ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? 'E' : 'W'}`;
}

/* Name of the cone under a point, if any. */
export function placeAt(x, z) {
  let best = null;
  let bestQ = 1.5;
  for (const c of CONES) {
    const q = ((x - c.x) ** 2 + (z - c.z) ** 2) / (c.r * c.r);
    if (q < bestQ) { bestQ = q; best = c.name; }
  }
  return best;
}

/* ---------------- 2D contour renderer (marching squares) ---------------- */

/* Edge pairs per marching-squares case. Edges: 0 top, 1 right, 2 bottom, 3 left. */
const CASES = [
  [], [[3, 2]], [[2, 1]], [[3, 1]], [[0, 1]], [[0, 1], [3, 2]], [[0, 2]], [[3, 0]],
  [[3, 0]], [[0, 2]], [[3, 0], [2, 1]], [[0, 1]], [[3, 1]], [[2, 1]], [[3, 2]], [],
];

/**
 * Draw contour lines of the shared height field into a canvas.
 * view: [x0, z0, x1, z1] window in map units (cover-fitted to the canvas).
 */
export function drawContours(canvas, opts = {}) {
  const {
    view = [-1, -1, 1, 1],
    line = 'rgba(0,0,0,.2)',
    index = 'rgba(0,0,0,.4)',
    route = null,
    showRoute = false,
    step = 5,
    interval = 20,
    width = 1,
  } = opts;

  const w = canvas.clientWidth;
  const hgt = canvas.clientHeight;
  if (!w || !hgt) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(hgt * dpr);
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, hgt);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  const [x0, z0, x1, z1] = view;
  const scale = Math.max(w / (x1 - x0), hgt / (z1 - z0));
  const cx = (x0 + x1) / 2;
  const cz = (z0 + z1) / 2;
  const cols = Math.ceil(w / step) + 2;
  const rows = Math.ceil(hgt / step) + 2;
  const f = new Float32Array(cols * rows);
  let max = -Infinity;
  for (let j = 0; j < rows; j++) {
    const mz = cz + (j * step - hgt / 2) / scale;
    for (let i = 0; i < cols; i++) {
      const v = heightAt(cx + (i * step - w / 2) / scale, mz);
      f[j * cols + i] = v;
      if (v > max) max = v;
    }
  }

  const pt = [0, 0];
  const edgePoint = (e, x, y, a, b, c, d, level) => {
    switch (e) {
      case 0: pt[0] = x + (step * (level - a)) / (b - a); pt[1] = y; break;
      case 1: pt[0] = x + step; pt[1] = y + (step * (level - b)) / (c - b); break;
      case 2: pt[0] = x + (step * (level - d)) / (c - d); pt[1] = y + step; break;
      default: pt[0] = x; pt[1] = y + (step * (level - a)) / (d - a);
    }
    return pt;
  };

  for (let level = 0; level <= max; level += interval) {
    const major = level % 100 === 0;
    ctx.beginPath();
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = f[j * cols + i];
        const b = f[j * cols + i + 1];
        const c = f[(j + 1) * cols + i + 1];
        const d = f[(j + 1) * cols + i];
        let idx = 0;
        if (a > level) idx |= 8;
        if (b > level) idx |= 4;
        if (c > level) idx |= 2;
        if (d > level) idx |= 1;
        const segs = CASES[idx];
        if (!segs.length) continue;
        const x = i * step;
        const y = j * step;
        for (const [e1, e2] of segs) {
          edgePoint(e1, x, y, a, b, c, d, level);
          ctx.moveTo(pt[0], pt[1]);
          edgePoint(e2, x, y, a, b, c, d, level);
          ctx.lineTo(pt[0], pt[1]);
        }
      }
    }
    ctx.strokeStyle = major ? index : line;
    ctx.lineWidth = major ? width * 1.6 : width;
    ctx.stroke();
  }

  if (showRoute && route) {
    const toPx = ([x, z]) => [(x - cx) * scale + w / 2, (z - cz) * scale + hgt / 2];
    ctx.save();
    ctx.strokeStyle = route;
    ctx.lineWidth = 2;
    ctx.setLineDash([7, 6]);
    ctx.beginPath();
    ROUTE.forEach((p, k) => {
      const [px, py] = toPx(p);
      if (k === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.setLineDash([]);
    for (const wp of WAYPOINTS) {
      const [px, py] = toPx([wp.x, wp.z]);
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI * 2);
      ctx.fillStyle = route;
      ctx.fill();
    }
    ctx.restore();
  }
}
