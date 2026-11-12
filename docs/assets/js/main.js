/* ------------------------------------------------------------------
   Aum Patel ePortfolio: page behaviour.
   Everything here is progressive: with JavaScript off, or with the
   CDN libraries blocked, the page still reads top to bottom.
   ------------------------------------------------------------------ */
import { drawContours } from './terrain.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const root = document.documentElement;
const mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
const mqDark = window.matchMedia('(prefers-color-scheme: dark)');
const reduced = mqReduce.matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
const store = {
  get(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } },
};

/* ---------------- theme ---------------- */
const themeListeners = new Set();
const currentTheme = () => {
  const t = root.getAttribute('data-theme');
  if (t === 'dark' || t === 'light') return t;
  return mqDark.matches ? 'dark' : 'light';
};
function emitTheme() {
  const t = currentTheme();
  const btn = $('.theme-toggle');
  if (btn) {
    btn.dataset.mode = t;
    btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }
  themeListeners.forEach((fn) => fn(t));
}
$('.theme-toggle')?.addEventListener('click', () => {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  store.set('ap-theme', next);
  root.setAttribute('data-theme', next);
});
mqDark.addEventListener?.('change', emitTheme);
new MutationObserver(emitTheme).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
emitTheme();

/* ---------------- header, progress, active section ---------------- */
const header = $('[data-header]');
const progress = $('.progress span');
function onScroll() {
  const y = window.scrollY;
  header?.classList.toggle('is-scrolled', y > 24);
  const max = document.documentElement.scrollHeight - window.innerHeight;
  if (progress) progress.style.transform = `scaleX(${max > 0 ? Math.min(1, y / max) : 0})`;
}
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

const navLinks = $$('[data-nav]');
const navTargets = navLinks.map((a) => $(a.getAttribute('href'))).filter(Boolean);
const navIO = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    navLinks.forEach((a) => {
      if (a.getAttribute('href') === `#${entry.target.id}`) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });
  });
}, { rootMargin: '-40% 0px -55% 0px' });
navTargets.forEach((s) => navIO.observe(s));

/* ---------------- smooth scrolling ---------------- */
let lenis = null;
const hasGsap = !!(window.gsap && window.ScrollTrigger);
if (hasGsap) window.gsap.registerPlugin(window.ScrollTrigger);
if (window.Lenis && !reduced) {
  lenis = new window.Lenis({ duration: 1.15, easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)) });
  if (hasGsap) {
    lenis.on('scroll', window.ScrollTrigger.update);
    window.gsap.ticker.add((t) => lenis.raf(t * 1000));
    window.gsap.ticker.lagSmoothing(0);
  } else {
    const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  }
}

function scrollToTarget(target) {
  const offset = -((header?.offsetHeight || 64) + 12);
  if (target === 'top') {
    if (lenis) lenis.scrollTo(0); else window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
    return;
  }
  if (lenis) lenis.scrollTo(target, { offset });
  else {
    const top = target.getBoundingClientRect().top + window.scrollY + offset;
    window.scrollTo({ top, behavior: reduced ? 'auto' : 'smooth' });
  }
  target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
}

document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const id = a.getAttribute('href');
  e.preventDefault();
  closeMenu();
  if (id === '#' || id === '#top') { scrollToTarget('top'); return; }
  const target = document.querySelector(id);
  if (target) scrollToTarget(target);
});

/* ---------------- mobile menu ---------------- */
const menuBtn = $('.menu-toggle');
const menu = $('#mobile-menu');
function openMenu() {
  if (!menu) return;
  menu.hidden = false;
  menuBtn.setAttribute('aria-expanded', 'true');
  menuBtn.setAttribute('aria-label', 'Close menu');
  document.body.classList.add('menu-open');
  lenis?.stop();
  menu.querySelector('a')?.focus();
}
function closeMenu() {
  if (!menu || menu.hidden) return;
  menu.hidden = true;
  menuBtn.setAttribute('aria-expanded', 'false');
  menuBtn.setAttribute('aria-label', 'Open menu');
  document.body.classList.remove('menu-open');
  lenis?.start();
}
menuBtn?.addEventListener('click', () => (menu.hidden ? openMenu() : closeMenu()));
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
window.matchMedia('(min-width: 900px)').addEventListener?.('change', closeMenu);

/* ---------------- Auckland clock ---------------- */
const fmtTime = new Intl.DateTimeFormat('en-NZ', { timeZone: 'Pacific/Auckland', hour: 'numeric', minute: '2-digit', hour12: true });
const fmtZone = new Intl.DateTimeFormat('en-NZ', { timeZone: 'Pacific/Auckland', timeZoneName: 'short' });
function tick() {
  const now = new Date();
  const zone = fmtZone.formatToParts(now).find((p) => p.type === 'timeZoneName')?.value || 'NZT';
  const text = `${fmtTime.format(now)} ${zone}`;
  $$('[data-nz-time]').forEach((el) => { el.textContent = text; });
}
tick();
setInterval(tick, 20000);

/* ---------------- contour panels ---------------- */
const CROPS = {
  hero: [-1, -1, 1, 1],
  portrait: [-0.34, -0.12, 0.24, 0.32],
  aspire: [-0.78, -0.82, 0.88, 0.8],
  banner: [0.15, -0.86, 0.85, -0.36],
  cover: [-0.08, 0.2, 0.46, 0.64],
  cover2: [0.18, -0.86, 0.86, -0.3],
  e1: [-0.3, -0.08, 0.08, 0.24],
  e2: [0.0, 0.26, 0.34, 0.58],
  e3: [-0.72, 0.06, -0.34, 0.4],
  e4: [0.4, 0.12, 0.8, 0.48],
  e5: [-0.5, 0.38, -0.14, 0.72],
  e6: [0.22, -0.88, 0.78, -0.32],
  contact: [-0.25, -0.95, 1.0, 0.05],
};

function contourTokens() {
  const cs = getComputedStyle(root);
  const g = (n) => cs.getPropertyValue(n).trim();
  return {
    line: g('--contour'), index: g('--contour-index'),
    lineInv: g('--contour-inv'), indexInv: g('--contour-inv-index'),
    route: g('--route'),
  };
}

const contourCanvases = new Set($$('canvas[data-contours]'));
function drawPanel(canvas, tokens = contourTokens()) {
  const inv = canvas.dataset.tone === 'inv';
  drawContours(canvas, {
    view: CROPS[canvas.dataset.contours] || CROPS.hero,
    line: inv ? tokens.lineInv : tokens.line,
    index: inv ? tokens.indexInv : tokens.index,
    route: tokens.route,
    showRoute: canvas.hasAttribute('data-route'),
    step: Number(canvas.dataset.step) || 5,
  });
}
function drawAllPanels() {
  const tokens = contourTokens();
  contourCanvases.forEach((c) => drawPanel(c, tokens));
}
const panelSizes = new WeakMap();
const panelRO = new ResizeObserver((entries) => {
  entries.forEach((entry) => {
    const c = entry.target;
    const size = `${Math.round(entry.contentRect.width)}x${Math.round(entry.contentRect.height)}`;
    if (panelSizes.get(c) === size) return;
    panelSizes.set(c, size);
    requestAnimationFrame(() => drawPanel(c));
  });
});
contourCanvases.forEach((c) => panelRO.observe(c));
themeListeners.add(() => requestAnimationFrame(drawAllPanels));
if (document.fonts?.ready) document.fonts.ready.then(() => requestAnimationFrame(drawAllPanels));

/* ---------------- hero map ---------------- */
const heroCanvas = $('#hero-canvas');
const hudPlace = $('#hud-place');
const hudCoords = $('#hud-coords');
const hudElev = $('#hud-elev');
const hudDefaults = {
  place: hudPlace?.textContent, coords: hudCoords?.textContent, elev: hudElev?.textContent,
};
const hud = {
  set({ place, coords, elev }) {
    if (hudPlace) hudPlace.textContent = place;
    if (hudCoords) hudCoords.textContent = coords;
    if (hudElev) hudElev.textContent = elev;
  },
  reset() { hud.set(hudDefaults); },
};

function heroFallback() {
  if (!heroCanvas) return;
  const flat = document.createElement('canvas');
  flat.className = heroCanvas.className;
  flat.dataset.contours = 'hero';
  flat.dataset.step = '6';
  flat.setAttribute('data-route', '');
  heroCanvas.replaceWith(flat);
  $('.hero')?.classList.add('hero--flat');
  contourCanvases.add(flat);
  panelRO.observe(flat);
}

if (heroCanvas) {
  import('./hero-map.js')
    .then((m) => m.initHeroMap({
      canvas: heroCanvas, labelsEl: $('#hero-labels'), host: $('.hero'), hud, reducedMotion: reduced,
    }))
    .then((api) => {
      if (!api) { heroFallback(); return; }
      themeListeners.add(() => api.applyTheme());
    })
    .catch(heroFallback);
}

/* ---------------- scroll-linked motion (GSAP) ---------------- */
if (hasGsap && !reduced) {
  const { gsap, ScrollTrigger } = window;
  const vh = window.innerHeight;

  // Content stays visible at rest; only elements that start below the fold
  // animate, and only once they reach the viewport.
  $$('[data-reveal]').forEach((el) => {
    if (el.getBoundingClientRect().top < vh) return;
    gsap.fromTo(el, { y: 40, autoAlpha: 0 }, {
      y: 0, autoAlpha: 1, duration: 1.1, ease: 'expo.out', immediateRender: false,
      scrollTrigger: { trigger: el, start: 'top bottom', once: true },
    });
  });

  $$('[data-reveal-group]').forEach((group) => {
    const items = Array.from(group.children);
    if (group.getBoundingClientRect().top < vh) return;
    gsap.fromTo(items, { y: 48, autoAlpha: 0 }, {
      y: 0, autoAlpha: 1, duration: 1.1, ease: 'expo.out', stagger: 0.08, immediateRender: false,
      scrollTrigger: { trigger: group, start: 'top bottom', once: true },
    });
  });

  const mm = gsap.matchMedia();
  mm.add('(min-width: 761px)', () => {
    $$('.route-steps__line').forEach((line) => {
      gsap.fromTo(line, { scaleX: 0 }, {
        scaleX: 1, ease: 'none',
        scrollTrigger: { trigger: line.parentElement, start: 'top 85%', end: 'bottom 55%', scrub: 0.6 },
      });
    });
    const sheet = $('.sheet');
    if (sheet) {
      gsap.fromTo(sheet, { rotateX: 10, y: 60, transformPerspective: 1600 }, {
        rotateX: 0, y: 0, ease: 'none',
        scrollTrigger: { trigger: sheet, start: 'top bottom', end: 'top 30%', scrub: 0.8 },
      });
    }
  });
  mm.add('(max-width: 760px)', () => {
    $$('.route-steps__line').forEach((line) => {
      gsap.fromTo(line, { scaleY: 0 }, {
        scaleY: 1, ease: 'none',
        scrollTrigger: { trigger: line.parentElement, start: 'top 80%', end: 'bottom 60%', scrub: 0.6 },
      });
    });
  });

  // Gentle parallax on decorative contour panels.
  $$('[data-parallax]').forEach((el) => {
    gsap.fromTo(el, { yPercent: -6 }, {
      yPercent: 6, ease: 'none',
      scrollTrigger: { trigger: el.parentElement, start: 'top bottom', end: 'bottom top', scrub: true },
    });
  });

  window.addEventListener('load', () => ScrollTrigger.refresh());
}

/* ---------------- tilt on cards ---------------- */
if (finePointer && !reduced) {
  $$('[data-tilt]').forEach((el) => {
    let frame = 0;
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.transform = `perspective(1000px) rotateX(${(-py * 6).toFixed(2)}deg) rotateY(${(px * 8).toFixed(2)}deg)`;
        el.style.setProperty('--gx', `${((px + 0.5) * 100).toFixed(1)}%`);
        el.style.setProperty('--gy', `${((py + 0.5) * 100).toFixed(1)}%`);
      });
    });
    el.addEventListener('pointerleave', () => {
      cancelAnimationFrame(frame);
      el.style.transform = '';
    });
  });
}

/* ---------------- case study step trackers (one per case study) ---------------- */
$$('.case').forEach((caseEl) => {
  const links = $$('.case__nav a', caseEl);
  if (!links.length) return;
  const marker = $('.case__nav .marker', caseEl);
  const setActive = (id) => {
    links.forEach((a) => {
      if (a.getAttribute('href') === `#${id}`) {
        a.setAttribute('aria-current', 'step');
        if (marker) {
          marker.style.transform = `translateY(${a.offsetTop}px)`;
          marker.style.height = `${a.offsetHeight}px`;
        }
      } else a.removeAttribute('aria-current');
    });
  };
  const stepIO = new IntersectionObserver((list) => {
    list.forEach((entry) => { if (entry.isIntersecting) setActive(entry.target.id); });
  }, { rootMargin: '-35% 0px -60% 0px' });
  links.forEach((a) => { const t = $(a.getAttribute('href')); if (t) stepIO.observe(t); });
  setActive(links[0].getAttribute('href').slice(1));
});

/* ---------------- journal reader ---------------- */
const reader = $('#reader');
const entries = $$('.entry');
if (reader && entries.length) {
  const rScroll = $('.reader__scroll', reader);
  const rTitle = $('#reader-title');
  const rKicker = $('#reader-kicker');
  const rMeta = $('#reader-meta');
  const rBody = $('#reader-body');
  const rBar = $('.reader__progress', reader);
  const rCount = $('#reader-count');
  let current = 0;

  const words = (el) => (el.textContent.trim().match(/\S+/g) || []).length;
  entries.forEach((entry) => {
    const n = words($('.entry__full', entry));
    const mins = Math.max(1, Math.round(n / 220));
    const rt = $('.entry__time', entry);
    if (rt) rt.textContent = `${mins} min read`;
    entry.dataset.minutes = String(mins);
  });

  const open = (i) => {
    current = (i + entries.length) % entries.length;
    const entry = entries[current];
    rKicker.textContent = entry.dataset.kicker || '';
    rTitle.innerHTML = $('.entry__title', entry).innerHTML;
    rMeta.textContent = `${$('.entry__course', entry)?.textContent || ''} · ${$('.entry__date', entry)?.textContent || ''} · ${entry.dataset.minutes} min read`;
    rBody.innerHTML = $('.entry__full', entry).innerHTML;
    reader.classList.toggle('reader--peer', entry.classList.contains('entry--peer'));
    if (rCount) rCount.textContent = `${current + 1} / ${entries.length}`;
    if (!reader.open) {
      reader.showModal();
      lenis?.stop();
      document.body.classList.add('reader-open');
    }
    rScroll.scrollTop = 0;
    updateBar();
    rTitle.focus({ preventScroll: true });
  };
  const updateBar = () => {
    const max = rScroll.scrollHeight - rScroll.clientHeight;
    rBar.style.transform = `scaleX(${max > 0 ? rScroll.scrollTop / max : 1})`;
  };

  entries.forEach((entry, i) => $('.entry__open', entry)?.addEventListener('click', () => open(i)));
  $('[data-reader-prev]', reader)?.addEventListener('click', () => open(current - 1));
  $('[data-reader-next]', reader)?.addEventListener('click', () => open(current + 1));
  $('[data-reader-close]', reader)?.addEventListener('click', () => reader.close());
  reader.addEventListener('click', (e) => { if (e.target === reader) reader.close(); });
  reader.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' && !e.target.closest('input, textarea')) open(current + 1);
    if (e.key === 'ArrowLeft' && !e.target.closest('input, textarea')) open(current - 1);
  });
  reader.addEventListener('close', () => {
    lenis?.start();
    document.body.classList.remove('reader-open');
    $('.entry__open', entries[current])?.focus({ preventScroll: true });
  });
  rScroll.addEventListener('scroll', updateBar, { passive: true });
}

/* ---------------- copy buttons ---------------- */
function selectText(el) {
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}
async function copyFrom(el, btn, okLabel = 'Copied') {
  const label = btn.dataset.label || btn.textContent;
  btn.dataset.label = label;
  const text = el.value ?? el.textContent.trim();
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = okLabel;
  } catch (err) {
    if (el.select) el.select(); else selectText(el);
    btn.textContent = 'Selected: press Ctrl+C';
  }
  setTimeout(() => { btn.textContent = label; }, 2200);
}
$$('[data-copy]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const el = $(btn.dataset.copy);
    if (el) copyFrom(el, btn);
  });
});

/* ---------------- contact form ---------------- */
const form = $('#contact-form');
if (form) {
  const status = $('.form__status', form);
  const fallback = $('#form-fallback');
  const composed = $('#composed-message');
  const mailLink = $('#composed-mail');
  const email = ($('#contact-email')?.textContent || '').trim();
  const fields = [
    { el: $('#cf-name'), msg: 'Please add your name.' },
    { el: $('#cf-email'), msg: 'Please add an email address I can reply to, like name@example.com.' },
    { el: $('#cf-message'), msg: 'Please write a short message.' },
  ];

  const validate = () => {
    let first = null;
    fields.forEach(({ el, msg }) => {
      const err = $(`#${el.id}-error`);
      const ok = el.checkValidity() && el.value.trim() !== '';
      el.setAttribute('aria-invalid', ok ? 'false' : 'true');
      if (err) err.textContent = ok ? '' : msg;
      if (!ok && !first) first = el;
    });
    if (first) first.focus();
    return !first;
  };

  fields.forEach(({ el }) => el.addEventListener('input', () => {
    if (el.getAttribute('aria-invalid') === 'true' && el.checkValidity() && el.value.trim()) {
      el.setAttribute('aria-invalid', 'false');
      const err = $(`#${el.id}-error`);
      if (err) err.textContent = '';
    }
  }));

  // Hand the visitor a ready-to-send email when the message can't go through the form.
  const offerEmail = (data, subject, note) => {
    const body = `${data.get('message')}\n\n${data.get('name')}\n${data.get('email')}`;
    composed.value = `To: ${email}\nSubject: ${subject}\n\n${body}`;
    mailLink.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    fallback.hidden = false;
    status.textContent = note;
    if (lenis) lenis.scrollTo(fallback, { offset: -window.innerHeight * 0.3 });
    else fallback.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
  };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validate()) return;
    const data = new FormData(form);
    const subject = `${data.get('topic') || 'General enquiry'} (via your ePortfolio)`;
    const endpoint = (form.dataset.endpoint || '').trim();
    const button = $('button[type="submit"]', form);

    if (!endpoint) {
      offerEmail(data, subject, 'Your message is ready. Copy it below and send it to my email address.');
      return;
    }
    if (form.dataset.sending) return;

    // aria-disabled rather than disabled, so keyboard focus stays on the button while sending.
    form.dataset.sending = '1';
    button.setAttribute('aria-disabled', 'true');
    status.textContent = 'Sending your message…';
    try {
      // FormSubmit's AJAX endpoint answers 200 with { success: "true" | "false" }.
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ ...Object.fromEntries(data), _subject: subject, _template: 'table' }),
      });
      const reply = await res.json().catch(() => ({}));
      if (!res.ok || String(reply.success) !== 'true') throw new Error(reply.message || String(res.status));
      status.textContent = `Thanks, ${data.get('name')}. Your message has been sent and I'll reply by email.`;
      fallback.hidden = true;
      form.reset();
    } catch (err) {
      offerEmail(data, subject, "Your message couldn't be sent from the form just now, so it's ready below: open it in your email app or copy it.");
    } finally {
      delete form.dataset.sending;
      button.removeAttribute('aria-disabled');
    }
  });

  $('#copy-composed')?.addEventListener('click', (e) => copyFrom(composed, e.currentTarget, 'Message copied'));
}

/* ---------------- placeholder tracker (draft aid) ---------------- */
const placeholders = $$('.ph');
const draft = $('#draft');
if (draft && placeholders.length && store.get('ap-draft-hidden') !== '1') {
  draft.hidden = false;
  $('#draft-count').textContent = String(placeholders.length);
  let k = -1;
  $('[data-draft-next]', draft).addEventListener('click', () => {
    k = (k + 1) % placeholders.length;
    const ph = placeholders[k];
    const host = ph.closest('.entry') || ph;
    const target = host.closest('[hidden]') ? host.parentElement : host;
    if (lenis) lenis.scrollTo(target, { offset: -window.innerHeight * 0.35 });
    else target.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
    host.classList.remove('is-flash');
    void host.offsetWidth;
    host.classList.add('is-flash');
    $('#draft-pos').textContent = `${k + 1}/${placeholders.length}`;
  });
  $('[data-draft-hide]', draft).addEventListener('click', () => {
    draft.hidden = true;
    store.set('ap-draft-hidden', '1');
  });
}

/* ---------------- misc ---------------- */
$$('[data-year]').forEach((el) => { el.textContent = String(new Date().getFullYear()); });
