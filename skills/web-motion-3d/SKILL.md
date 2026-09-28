---
name: web-motion-3d
description: Design and build motion-rich, interactive 3D websites - scroll-driven animation, WebGL product viewers, stitch/line-drawing effects, and micro-interactions - that stay fast and accessible. Use when asked for animation, scroll effects, parallax, a 3D hero or product viewer, Three.js, GSAP, "make the site feel alive/premium", or a showcase site for a craft or product business such as embroidery, apparel, or textiles.
---

# Web motion and interactive 3D

Motion is there to show off the product and guide the eye, not to decorate. Every
animation must answer "what does this help the visitor notice or do?" If there is
no answer, cut it.

## Before writing anything

1. Find out what the business actually sells and what a visitor must do (browse
   designs, request a quote, order, call). The hero and every animated section
   lead toward that action.
2. Collect the real assets: product photos, logo (ideally SVG), design files. For
   an embroidery business, ask for close-up macro shots of stitching and any
   `.svg`/`.ai` artwork of logos they have stitched - these drive the best effects.
3. Check the stack. Match what exists (React, Next, Astro, plain HTML). Default
   for a new marketing site: plain HTML/CSS + GSAP + Three.js loaded as ES modules,
   or Vite if a build step is acceptable.

## Tool choice

| Need | Use |
| --- | --- |
| Hover, focus, simple reveals | CSS transitions + `@keyframes` |
| Scroll-linked reveals, pinning, timelines | GSAP + ScrollTrigger |
| Smooth scrolling feel | Lenis (optional; never hijack scroll with custom wheel math) |
| Native scroll-linked effects, no JS | CSS `animation-timeline: view()` with a JS fallback |
| 3D models, fabric, lighting | Three.js (or `@react-three/fiber` + `drei` in React) |
| Page transitions | View Transitions API, falling back to instant navigation |

Load from `cdn.jsdelivr.net/npm/...` or install via npm. Pin versions.

## Motion rules

- Durations: 150-250 ms for UI feedback, 400-800 ms for reveals, longer only for
  scroll-scrubbed sequences. Easing: `power2.out` / `cubic-bezier(.2,.7,.2,1)` for
  entrances; never linear except for scrubbed or looping motion.
- Animate only `transform` and `opacity` (and `stroke-dashoffset`, `clip-path` in
  moderation). Never animate `width`, `height`, `top`, `left`, or box-shadow on
  large elements.
- Stagger groups (50-90 ms apart) instead of moving everything at once.
- One hero moment per viewport. Competing animations cancel each other out.
- Content must be readable and clickable before any animation finishes. Never
  hide the primary call-to-action behind a reveal.

## Accessibility is not optional

Wrap all non-essential motion:

```js
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
if (!reduce) initMotion();   // otherwise render the final state directly
```

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
```

- 3D canvases get `role="img"` and an `aria-label` describing the product, plus a
  static image fallback if WebGL is unavailable.
- Nothing flashes more than 3 times per second.
- Interactive 3D (drag to rotate) must also work with buttons or keys.

## 3D with Three.js

- Keep the scene small: one hero model, 2-3 lights, an environment map
  (`RoomEnvironment` or a small HDRI). Target under 2 MB of 3D assets total.
- Compress models: glTF/GLB with Draco or Meshopt, textures as KTX2 or WebP,
  max 2048 px.
- `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))`. Pause the render loop
  when the canvas is off-screen (`IntersectionObserver`) or the tab is hidden.
- Lazy-load the 3D bundle after first paint; show a poster image meanwhile.
- On phones, lower geometry detail and drop post-processing. Test at 360 px wide.

## Embroidery and textile recipes

These are the effects that make a stitching business's site feel crafted:

1. **Stitch-drawing logo.** Convert the logo/artwork to SVG paths, give strokes a
   dashed pattern (`stroke-dasharray: 6 4`) to look like running stitches, then
   reveal by animating a mask path's `stroke-dashoffset` from its length to 0 on
   scroll. Reads as "being sewn in front of you".
2. **Thread that follows the scroll.** A single SVG path winding down the page,
   drawn progressively with ScrollTrigger `scrub: true`, connecting sections like
   a thread through fabric.
3. **3D hoop / garment viewer.** A GLB of a hoop, cap, or t-shirt with the
   customer's design as a texture. Use a fabric normal map (weave pattern) and
   a separate thread-sheen normal map on the design area so the stitches catch
   the light as the model rotates. `OrbitControls` with damping, zoom limited,
   auto-rotate slowly until the user interacts.
4. **Macro-zoom reveal.** Pin a section and scrub from a full product photo to a
   close-up of the stitching (scale + clip-path), with a caption about stitch
   count or thread quality.
5. **Tactile hover.** On design cards, tilt slightly toward the cursor (max 6-8
   degrees) and shift a highlight gradient across the image to suggest raised
   thread. Disable on touch devices.
6. **Colour-thread picker.** Swatches that recolour the design on the 3D model
   live (swap material colour or texture), useful for quote requests.

Palette guidance: let the products supply the colour. Use a quiet base (linen,
off-white, charcoal) and one thread-coloured accent for calls-to-action.

## Page skeleton for a craft/business showcase

1. Hero: stitch-drawing logo or 3D hoop, one headline, one CTA ("Get a quote").
2. Services (logos, names, patches, custom apparel) with staggered reveals.
3. Process: pinned scroll story - artwork, digitising, stitching, finished piece.
4. Gallery: filterable grid with tactile hover; opens a lightbox or 3D view.
5. Social proof: reviews, clients, numbers (count-up only once, when visible).
6. Contact/quote form with upload for artwork. No animation on form fields
   beyond focus states.

## Performance budget

- Largest Contentful Paint under 2.5 s on mid-range mobile; the LCP element is a
  real image or headline, never a WebGL canvas.
- JavaScript for motion + 3D under ~250 KB gzipped before the model loads.
- Keep 60 fps while scrolling: check the Performance panel for long tasks and
  layout thrashing. Kill any ScrollTrigger you create on route change
  (`ScrollTrigger.getAll().forEach(t => t.kill())` or `gsap.context().revert()`).

## Before you call it done

- Scroll the whole page on a phone-sized viewport and on desktop.
- Turn on reduced motion in the OS and confirm the page still makes sense.
- Disable WebGL (or throttle to slow 3G) and confirm the fallback image appears.
- Tab through every interactive element, including the 3D controls.
- Check the console is clean and nothing keeps animating off-screen.
