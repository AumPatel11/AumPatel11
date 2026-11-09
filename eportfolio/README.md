# Aum Patel ePortfolio

A single-page ePortfolio for ICL Graduate Business School, built as a plain static site
(HTML, CSS and JavaScript, no build step). It covers every part of the brief:

| Brief section | Where it lives on the page |
| --- | --- |
| Biographical: introduction, career aspirations | `#biography`: Personal introduction, Career aspirations |
| Biographical: self-evaluation (Whetten & Cameron ch. 1) | `#self-evaluation` |
| Biographical: LinkedIn link | `#linkedin` |
| Biographical: contact details and form | `#contact` |
| Project work | `#project`: two case studies in seven steps each, Oven Fresh Bakery (`#case-ovenfresh`) and AussieStitch (`#case-aussiestitch`) |
| Professional development: PPLG | `#pplg` (personal goals P1–P3, professional goals C1–C3) |
| Professional development: CV (NZ format) | `#cv` |
| Reflective learning: five posts + peer evaluation | `#reflections` (cards open in a reader) |

## Design

The page is styled as a surveyor's field map of Auckland. The hero is a live 3D contour map
of a stylised Auckland volcanic field (Maungawhau, Maungakiekie, Rangitoto and others, with
their real summit heights) with a crimson career route running from **Now** to **Vision**.
Point at the map and the readout shows the place, coordinates and elevation. The same
height field draws the contour panels used throughout the page.

- Light and dark themes (follows the device setting; the sun/moon button overrides it).
- Smooth scrolling, scroll-triggered reveals and card tilt; all switched off for visitors
  who ask their device for reduced motion.
- If WebGL or the CDN is unavailable, the hero falls back to a flat contour map, and every
  section still reads normally without JavaScript.

## Filling in your details

Every piece of text you still need to write is wrapped in `<span class="ph">[...]</span>`
and shows with a red dashed underline. While any remain, a small counter in the bottom-left
corner says how many are left; select it to jump to the next one. When you replace a
placeholder, delete the `<span class="ph">` wrapper too. The counter disappears by itself
once none are left.

Things to update in `index.html`:

1. **Photo**: put your photo at `assets/img/aum-patel.jpg` and replace the
   `portrait__placeholder` block with the `<img>` tag shown in the comment above it.
2. **LinkedIn**: replace `https://www.linkedin.com/in/your-profile` (two places).
3. **Email**: replace `your.name@email.com` in the contact section and the CV.
4. **Contact form**: create a free form at [formspree.io](https://formspree.io), then paste
   its URL into `data-endpoint=""` on `<form id="contact-form">`. Until then, the form gives
   visitors a ready-made message to copy and email to you.
5. **CV as PDF** (optional): add the link where the comment in the CV section shows.
6. **Reflections**: each journal card has a title, a one-line excerpt and a hidden
   `entry__full` block with three headings (What I learned, Why it was useful, How I'm
   applying it). Aim for 200–350 words per post. Reading time is calculated automatically.

## Previewing locally

Any static server works, for example:

```bash
cd eportfolio && python3 -m http.server 8000
```

Then open http://localhost:8000. Opening `index.html` straight from the file system will not
load the scripts, because browsers block ES modules on `file://` URLs.

## Publishing

- **Netlify Drop**: drag the `eportfolio` folder onto https://app.netlify.com/drop.
- **GitHub Pages**: Pages serves from the repository root or `/docs`, so either copy this
  folder's contents into `/docs` or publish it with a Pages workflow.

The brief suggests Wix or WordPress; check with your lecturer that a custom site is
acceptable before you submit.

## Files

```
eportfolio/
├── index.html            all page content
├── assets/css/styles.css design tokens (light and dark), layout and components
└── assets/js/
    ├── main.js           theme, navigation, scrolling, reader, form, contour panels
    ├── hero-map.js       three.js 3D contour map in the hero
    └── terrain.js        shared Auckland height field and 2D contour renderer
```

Libraries load from public CDNs, pinned to exact versions: three.js 0.160.0, GSAP 3.12.5
(with ScrollTrigger) and Lenis 1.1.13. Fonts are Archivo, Newsreader and Martian Mono
from Google Fonts.
