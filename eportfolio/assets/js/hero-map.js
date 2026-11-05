/* ------------------------------------------------------------------
   Hero: a 3D contour map of a stylised Auckland volcanic field with
   the career route drawn across it. Built with three.js; if WebGL or
   the CDN is unavailable, initHeroMap resolves false and main.js
   draws a flat contour map instead.
   ------------------------------------------------------------------ */
import {
  heightAt, coastDist, CONES, ROUTE, WAYPOINTS, toLatLon, formatLatLon, placeAt,
} from './terrain.js';

const THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
const SIZE = 4;
const HALF = SIZE / 2;
const VERT = 0.72 / 260; // vertical exaggeration: 260 m -> 0.72 world units

const vertexShader = /* glsl */ `
  attribute float aH;
  attribute float aD;
  varying float vH;
  varying float vD;
  varying vec3 vWorld;
  varying float vDepth;
  void main() {
    vH = aH;
    vD = aD;
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vWorld = wp.xyz;
    vec4 mv = viewMatrix * wp;
    vDepth = -mv.z;
    gl_Position = projectionMatrix * mv;
  }
`;

const fragmentShader = /* glsl */ `
  uniform vec3 uInk;
  uniform vec3 uRoute;
  uniform float uTime;
  uniform float uReveal;
  uniform vec3 uHover;
  uniform float uHoverOn;
  uniform vec3 uPing;
  uniform float uPingOn;
  uniform float uDark;
  uniform vec2 uFog;
  varying float vH;
  varying float vD;
  varying vec3 vWorld;
  varying float vDepth;

  // Anti-aliased iso-line: 1.0 on the line, 0.0 elsewhere.
  float iso(float v, float w) {
    float fw = max(fwidth(v), 1e-5);
    float g = abs(fract(v - 0.5) - 0.5) / fw;
    return 1.0 - smoothstep(w - 0.6, w + 0.6, g);
  }

  void main() {
    vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
    float a = 0.0;

    if (vH >= 0.0) {
      float minor = iso(vH / 20.0, 0.75);
      float major = iso(vH / 100.0, 1.35);
      a = max(minor * 0.5, major * 0.95);
      float coast = 1.0 - smoothstep(0.0, 2.2 * fwidth(vH), vH);
      a = max(a, coast * 0.85);
      vec3 L = normalize(vec3(-0.55, 0.75, 0.35));
      float lit = clamp(dot(n, L), 0.0, 1.0);
      float shade = mix(1.0 - lit, lit, uDark);
      a = max(a, shade * mix(0.13, 0.07, uDark));
    } else {
      // Cartographic water-lining, parallel to the shore.
      float w = sqrt(max(-vD, 0.0)) * 24.0;
      a = iso(w, 0.65) * 0.32 * (1.0 - smoothstep(0.2, 1.0, -vD));
    }

    vec3 col = uInk;

    // Hover lens: lines near the pointer pick up the route colour.
    float dh = distance(vWorld.xz, uHover.xz);
    float lens = (1.0 - smoothstep(0.05, 0.5, dh)) * uHoverOn;
    col = mix(col, uRoute, lens * 0.9);
    a *= 1.0 + lens * 0.9;

    // "You are here" ping travelling outwards from the first waypoint.
    float t = fract(uTime / 6.0);
    float ring = abs(distance(vWorld.xz, uPing.xz) - t * 3.2);
    float ping = (1.0 - smoothstep(0.0, 0.07, ring)) * (1.0 - t) * uPingOn;
    col = mix(col, uRoute, ping);
    a *= 1.0 + ping * 1.4;

    // Edge vignette, distance fade and the intro reveal sweep.
    float edge = 1.0 - smoothstep(1.45, 2.0, max(abs(vWorld.x), abs(vWorld.z)));
    float fog = 1.0 - smoothstep(uFog.x, uFog.y, vDepth);
    float sweep = (2.0 - vWorld.z) / 4.0;
    float reveal = 1.0 - smoothstep(uReveal - 0.18, uReveal, sweep);

    gl_FragColor = vec4(col, clamp(a, 0.0, 1.0) * edge * fog * reveal);
  }
`;

/* Camera orientations (orbit around the middle of the route, in degrees).
   Size and position on screen are not hand-tuned: fit() measures the free
   space around the page text and zooms the camera so the whole route and its
   labels land inside it. "side" puts the map beside the headline, "above"
   puts it above the text. */
const LAYOUTS = {
  wide: { mode: 'side', fov: 28, target: [0.38, 0.15, 0.08], dist: 6.7, elev: 37, azim: 16 },
  mid: { mode: 'above', fov: 30, target: [0.38, 0.15, 0.08], dist: 7.4, elev: 44, azim: 18 },
  tall: { mode: 'above', fov: 34, target: [0.38, 0.15, 0.08], dist: 9.5, elev: 50, azim: 20 },
};

function orbit(out, t, dist, elevDeg, azimDeg) {
  const e = (elevDeg * Math.PI) / 180;
  const a = (azimDeg * Math.PI) / 180;
  return out.set(
    t.x + dist * Math.sin(a) * Math.cos(e),
    t.y + dist * Math.sin(e),
    t.z + dist * Math.cos(a) * Math.cos(e),
  );
}

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const clamp01 = (t) => Math.min(1, Math.max(0, t));

export async function initHeroMap({ canvas, labelsEl, host, hud, reducedMotion }) {
  let THREE;
  try {
    THREE = await import(THREE_URL);
  } catch (err) {
    return null;
  }

  THREE.ColorManagement.enabled = false;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (err) {
    return null;
  }
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);
  const target = new THREE.Vector3();

  /* ---------- terrain ---------- */
  const small = Math.min(window.screen.width, window.screen.height) < 700;
  const SEG = small ? 170 : 260;
  const geo = new THREE.PlaneGeometry(SIZE, SIZE, SEG, SEG);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  const aH = new Float32Array(pos.count);
  const aD = new Float32Array(pos.count);
  for (let i = 0; i < pos.count; i++) {
    const mx = pos.getX(i) / HALF;
    const mz = pos.getZ(i) / HALF;
    const h = heightAt(mx, mz);
    aH[i] = h;
    aD[i] = coastDist(mx, mz);
    pos.setY(i, Math.max(h, 0) * VERT);
  }
  geo.setAttribute('aH', new THREE.BufferAttribute(aH, 1));
  geo.setAttribute('aD', new THREE.BufferAttribute(aD, 1));
  geo.computeBoundingSphere();

  const surf = (x, z, lift = 0.012) =>
    new THREE.Vector3(x * HALF, Math.max(heightAt(x, z), 0) * VERT + lift, z * HALF);

  const uniforms = {
    uInk: { value: new THREE.Color('#0F1E25') },
    uRoute: { value: new THREE.Color('#CF2338') },
    uTime: { value: 0 },
    uReveal: { value: 0 },
    uHover: { value: new THREE.Vector3(9, 0, 9) },
    uHoverOn: { value: 0 },
    uPing: { value: surf(WAYPOINTS[0].x, WAYPOINTS[0].z) },
    uPingOn: { value: reducedMotion ? 0 : 1 },
    uDark: { value: 0 },
    uFog: { value: new THREE.Vector2(4.5, 8.5) },
  };
  const terrainMat = new THREE.ShaderMaterial({
    uniforms, vertexShader, fragmentShader, transparent: true, depthWrite: true,
  });
  const terrain = new THREE.Mesh(geo, terrainMat);
  terrain.renderOrder = 0;
  scene.add(terrain);

  /* ---------- route ---------- */
  const flat = new THREE.CatmullRomCurve3(ROUTE.map(([x, z]) => new THREE.Vector3(x, 0, z)), false, 'centripetal');
  const routeCurve = new THREE.CatmullRomCurve3(flat.getSpacedPoints(520).map((p) => surf(p.x, p.z, 0.014)));
  const tubeGeo = new THREE.TubeGeometry(routeCurve, 720, 0.009, 8, false);
  const routeMat = new THREE.MeshBasicMaterial({ color: 0xcf2338, transparent: true, depthWrite: false });
  const route = new THREE.Mesh(tubeGeo, routeMat);
  route.renderOrder = 2;
  scene.add(route);
  const routeCount = tubeGeo.index.count;

  const traveller = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 12), routeMat);
  traveller.renderOrder = 3;
  traveller.visible = !reducedMotion;
  scene.add(traveller);

  /* ---------- waypoint pins + labels ---------- */
  const pinGeo = new THREE.CylinderGeometry(0.0035, 0.0035, 1, 6);
  pinGeo.translate(0, 0.5, 0);
  const ringGeo = new THREE.RingGeometry(0.028, 0.04, 40);
  ringGeo.rotateX(-Math.PI / 2);
  const headGeo = new THREE.SphereGeometry(0.016, 16, 12);
  const pins = [];
  const labels = [];
  const sweepOf = (z) => (2 - z * HALF) / 4;

  WAYPOINTS.forEach((w, i) => {
    const base = surf(w.x, w.z, 0.004);
    const stemH = 0.2 + i * 0.035;
    const stem = new THREE.Mesh(pinGeo, routeMat);
    stem.position.copy(base);
    const ring = new THREE.Mesh(ringGeo, routeMat);
    ring.position.copy(base);
    const head = new THREE.Mesh(headGeo, routeMat);
    [stem, ring, head].forEach((m) => { m.renderOrder = 3; scene.add(m); });
    pins.push({ stem, ring, head, base, stemH, delay: 0.42 + i * 0.12 });

    const el = document.createElement('div');
    el.className = 'map-label map-label--wp';
    el.innerHTML = `<div class="map-label__box"><span class="map-label__n">${w.n}</span><span class="map-label__t">${w.label}</span><span class="map-label__p">${w.place}</span></div>`;
    labelsEl.appendChild(el);
    labels.push({ el, box: el.firstElementChild, world: base.clone().add(new THREE.Vector3(0, stemH + 0.03, 0)), at: 0.5 + i * 0.12, kind: 'wp' });
  });

  const spotCones = new Set(['Ōwairaka', 'Maungarei', 'Puketāpapa']);
  CONES.filter((c) => spotCones.has(c.name)).forEach((c) => {
    const el = document.createElement('div');
    el.className = 'map-label map-label--spot';
    el.innerHTML = `<div class="map-label__box"><span aria-hidden="true">▲</span> ${c.h}<span class="map-label__name">${c.name}</span></div>`;
    labelsEl.appendChild(el);
    labels.push({ el, world: surf(c.x, c.z, 0.03), at: sweepOf(c.z) + 0.05, kind: 'spot' });
  });

  {
    const el = document.createElement('div');
    el.className = 'map-label map-label--water';
    el.innerHTML = '<div class="map-label__box">Waitematā Harbour</div>';
    labelsEl.appendChild(el);
    labels.push({ el, world: new THREE.Vector3(-0.2 * HALF, 0.01, -0.52 * HALF), at: 0.75, kind: 'water' });
  }

  /* ---------- layout: fit the route into the free space ---------- */
  let W = 1;
  let H = 1;
  let layout = LAYOUTS.wide;
  let safe = { l: 0, r: 1, t: 0, b: 1 };
  const v = new THREE.Vector3();
  const fitPoints = routeCurve.points.filter((_, i) => i % 20 === 0);
  pins.forEach((pin) => fitPoints.push(pin.base, pin.base.clone().add(new THREE.Vector3(0, pin.stemH, 0))));
  const wpLabels = labels.filter((L) => L.kind === 'wp');
  const page = host;
  const headerEl = document.querySelector('[data-header]');
  const copyEl = page.querySelector('.hero__copy');
  const footEl = page.querySelector('.hero__foot');
  const titleSpans = Array.from(page.querySelectorAll('.hero__title .line > span'));

  // Free space inside the canvas, in canvas pixels. Offsets ignore CSS
  // transforms, so the intro animation does not skew the measurement.
  function freeSpace() {
    const top = (headerEl ? headerEl.offsetHeight : 64) + 14;
    const beside = () => {
      const titleRight = titleSpans.reduce((m, el) => Math.max(m, el.offsetLeft + el.offsetWidth), 0);
      const labelsLeft = Math.min(W * 0.72, titleRight + 20);
      const pointsLeft = Math.min(labelsLeft, Math.max(W * 0.42, titleRight - W * 0.1));
      const bottom = (footEl ? footEl.offsetTop : H) - 20;
      return { l: pointsLeft, labelShift: labelsLeft - pointsLeft, r: W - 28, t: top, b: Math.max(top + 200, bottom) };
    };
    const above = () => {
      const copyTop = copyEl ? copyEl.offsetTop : H * 0.5;
      return { l: 16, labelShift: 0, r: W - 16, t: top, b: Math.min(H - 12, copyTop - 22) };
    };
    if (layout.mode === 'side') return beside();
    // Prefer the band above the text; if the text leaves no room there
    // (landscape phones), use the space beside the headline instead.
    const a = above();
    if (a.b - a.t >= 200) return a;
    const b = beside();
    if (b.r - b.l - b.labelShift >= 220) return b;
    a.b = Math.min(H - 12, top + 200);
    return a;
  }

  function bounds(labelShift) {
    let l = Infinity;
    let r = -Infinity;
    let t = Infinity;
    let b = -Infinity;
    const add = (x, y) => {
      if (x < l) l = x;
      if (x > r) r = x;
      if (y < t) t = y;
      if (y > b) b = y;
    };
    for (const p of fitPoints) {
      v.copy(p).project(camera);
      add((v.x * 0.5 + 0.5) * W, (-v.y * 0.5 + 0.5) * H);
    }
    for (const L of wpLabels) {
      v.copy(L.world).project(camera);
      const x = (v.x * 0.5 + 0.5) * W;
      const y = (-v.y * 0.5 + 0.5) * H;
      const bw = L.box.offsetWidth || 120;
      const bh = L.box.offsetHeight || 36;
      add(x - bw / 2 - labelShift, y - 10 - bh);
      add(x + bw / 2, y);
    }
    return { l, r, t, b };
  }

  function fit() {
    safe = freeSpace();
    camera.fov = layout.fov;
    camera.aspect = W / H;
    camera.zoom = 1;
    camera.clearViewOffset();
    orbit(camera.position, target, layout.dist, layout.elev, layout.azim);
    camera.lookAt(target);
    camera.updateMatrixWorld();
    camera.updateProjectionMatrix();
    let zoom = 1;
    let box;
    for (let k = 0; k < 8; k++) {
      camera.zoom = zoom;
      camera.updateProjectionMatrix();
      box = bounds(safe.labelShift);
      const f = Math.min((safe.r - safe.l) / (box.r - box.l), (safe.b - safe.t) / (box.b - box.t));
      if (Math.abs(f - 1) < 0.004) break;
      zoom = Math.min(4, Math.max(0.2, zoom * f));
    }
    camera.zoom = zoom;
    camera.updateProjectionMatrix();
    box = bounds(safe.labelShift);
    camera.setViewOffset(W, H, (box.l + box.r) / 2 - (safe.l + safe.r) / 2, (box.t + box.b) / 2 - (safe.t + safe.b) / 2, W, H);
    camera.updateProjectionMatrix();
  }

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    W = Math.max(1, Math.round(rect.width));
    H = Math.max(1, Math.round(rect.height));
    renderer.setSize(W, H, false);
    layout = W >= 1000 && W / H > 1.15 ? LAYOUTS.wide : W / H < 0.95 ? LAYOUTS.tall : LAYOUTS.mid;
    target.set(...layout.target);
    uniforms.uFog.value.set(layout.dist - 1.8, layout.dist + 2.8);
    measureLabels();
    fit();
    requestRender();
  }

  /* ---------- theme ---------- */
  function applyTheme() {
    const cs = getComputedStyle(document.documentElement);
    const ink = cs.getPropertyValue('--ink').trim() || '#0F1E25';
    const red = cs.getPropertyValue('--route').trim() || '#CF2338';
    uniforms.uInk.value.set(ink);
    uniforms.uRoute.value.set(red);
    routeMat.color.set(red);
    const c = uniforms.uInk.value;
    uniforms.uDark.value = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b > 0.5 ? 1 : 0;
    requestRender();
  }

  /* ---------- pointer: march the view ray across the height field ---------- */
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let hoverTarget = 0;
  let pointerX = 0;
  let pointerY = 0;

  function pick(clientX, clientY) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const o = raycaster.ray.origin;
    const d = raycaster.ray.direction;
    const groundAt = (t) => {
      const x = o.x + d.x * t;
      const z = o.z + d.z * t;
      return { x, z, y: o.y + d.y * t, ty: Math.max(heightAt(x / HALF, z / HALF), 0) * VERT };
    };
    let prev = 0.3;
    for (let t = 0.3; t < 14; t += 0.02) {
      const p = groundAt(t);
      if (p.y <= p.ty) {
        let lo = prev;
        let hi = t;
        for (let k = 0; k < 14; k++) {
          const m = (lo + hi) / 2;
          const q = groundAt(m);
          if (q.y <= q.ty) hi = m; else lo = m;
        }
        const hit = groundAt(hi);
        if (Math.abs(hit.x) > HALF * 0.92 || Math.abs(hit.z) > HALF * 0.92) return null;
        return hit;
      }
      prev = t;
    }
    return null;
  }

  function onMove(e) {
    const r = host.getBoundingClientRect();
    pointerX = ((e.clientX - r.left) / r.width) * 2 - 1;
    pointerY = ((e.clientY - r.top) / r.height) * 2 - 1;
    const hit = pick(e.clientX, e.clientY);
    if (!hit) { onLeave(); return; }
    uniforms.uHover.value.set(hit.x, 0, hit.z);
    hoverTarget = 1;
    const mx = hit.x / HALF;
    const mz = hit.z / HALF;
    const h = heightAt(mx, mz);
    const name = placeAt(mx, mz);
    hud.set({
      place: h < 0 ? 'Waitematā Harbour' : name || 'Tāmaki Makaurau Auckland',
      coords: formatLatLon(toLatLon(mx, mz)),
      elev: h < 0 ? 'Sea level' : `${Math.round(h)} m`,
    });
    requestRender();
  }

  function onLeave() {
    hoverTarget = 0;
    hud.reset();
    requestRender();
  }

  host.addEventListener('pointermove', onMove, { passive: true });
  host.addEventListener('pointerdown', onMove, { passive: true });
  host.addEventListener('pointerleave', onLeave);

  /* ---------- labels ---------- */
  // Label sizes, measured once per layout so the frame loop never forces layout.
  function measureLabels() {
    for (const L of labels) {
      const box = L.el.firstElementChild;
      L.w = box.offsetWidth;
      L.h = box.offsetHeight;
    }
  }

  const wpRects = [];
  function placeLabels(progress) {
    wpRects.length = 0;
    for (const L of labels) {
      v.copy(L.world).project(camera);
      const x = (v.x * 0.5 + 0.5) * W;
      const y = (-v.y * 0.5 + 0.5) * H;
      let show = v.z < 1 && x > -40 && x < W + 40 && y > -20 && y < H + 20;
      if (L.kind === 'wp') {
        wpRects.push([x - L.w / 2 - 6, y - 10 - L.h - 6, x + L.w / 2 + 6, y + 6]);
      } else {
        // Small labels only show inside the free space, never behind the
        // page text and never on top of a waypoint label.
        const l = x - L.w / 2;
        const t = y - L.h / 2;
        show = show && x > safe.l + safe.labelShift && x < W - 20 && y > safe.t && y < safe.b
          && !wpRects.some((r) => l < r[2] && l + L.w > r[0] && t < r[3] && t + L.h > r[1]);
      }
      const alpha = clamp01((progress - L.at) * 10);
      L.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      L.el.style.opacity = show ? alpha.toFixed(3) : '0';
    }
  }

  /* ---------- animation ---------- */
  const INTRO = 2.8;
  let elapsed = reducedMotion ? INTRO : 0;
  let time = 0;
  let last = performance.now();
  let running = false;
  let inView = true;
  let pending = false;
  const parallax = { x: 0, y: 0 };

  function update(dt) {
    elapsed = Math.min(INTRO, elapsed + dt);
    time += dt;
    const p = elapsed / INTRO;
    const e = easeInOut(clamp01(p / 0.9));

    uniforms.uTime.value = time;
    uniforms.uReveal.value = clamp01(p * 1.35) * 1.25;
    uniforms.uHoverOn.value += (hoverTarget - uniforms.uHoverOn.value) * Math.min(1, dt * 8);

    const draw = clamp01((p - 0.28) / 0.62);
    tubeGeo.setDrawRange(0, Math.floor((routeCount * easeInOut(draw)) / 3) * 3);

    for (const pin of pins) {
      const s = easeInOut(clamp01((p - pin.delay) / 0.2));
      pin.stem.scale.set(1, Math.max(0.0001, pin.stemH * s), 1);
      pin.ring.scale.setScalar(Math.max(0.0001, s));
      pin.head.position.copy(pin.base).add(v.set(0, pin.stemH * s, 0));
      pin.head.scale.setScalar(Math.max(0.0001, s));
    }

    if (!reducedMotion) {
      const tt = (time / 9) % 1;
      traveller.visible = draw >= 1;
      traveller.position.copy(routeCurve.getPointAt(tt));
      traveller.scale.setScalar(0.6 + Math.sin(tt * Math.PI) * 0.6);
      parallax.x += (pointerX * 3 - parallax.x) * Math.min(1, dt * 2.5);
      parallax.y += (-pointerY * 1.5 - parallax.y) * Math.min(1, dt * 2.5);
    }

    // Intro: swing down from a high, distant view into the oblique map view.
    const dist = layout.dist * (1 + 0.35 * (1 - e));
    const elev = layout.elev + 30 * (1 - e) + parallax.y;
    const azim = layout.azim - 28 * (1 - e) + parallax.x;
    orbit(camera.position, target, dist, elev, azim);
    camera.lookAt(target);
    return p;
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const p = update(dt);
    renderer.render(scene, camera);
    placeLabels(p);
  }

  function loop(now) {
    if (!running) return;
    frame(now);
    requestAnimationFrame(loop);
  }

  function start() {
    if (running || reducedMotion || !inView || document.hidden) return;
    running = true;
    last = performance.now();
    requestAnimationFrame(loop);
  }

  function stop() { running = false; }

  function requestRender() {
    if (running || pending) return;
    pending = true;
    requestAnimationFrame((now) => { pending = false; last = now; frame(now); });
  }

  new IntersectionObserver((entries) => {
    inView = entries[0].isIntersecting;
    if (inView) start(); else stop();
  }).observe(canvas);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  new ResizeObserver(resize).observe(canvas.parentElement);

  applyTheme();
  resize();
  document.fonts?.ready.then(resize);
  window.addEventListener('load', resize);
  frame(performance.now());
  start();

  return { applyTheme, requestRender };
}
