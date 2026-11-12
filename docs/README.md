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
| Reflective learning: five posts | `#reflections` (cards open in a reader) |

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
2. **LinkedIn**: linked to linkedin.com/in/aum-patel-95086b356 (the LinkedIn card, the contact section and the CV). Change all three if the address changes.
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
cd docs && python3 -m http.server 8000
```

Then open http://localhost:8000. Opening `index.html` straight from the file system will not
load the scripts, because browsers block ES modules on `file://` URLs.

## Publishing: GitHub Pages and a free domain

The site lives in `/docs` so GitHub Pages can serve it as it is. `.nojekyll` tells Pages to
publish the files unchanged.

1. **Turn on GitHub Pages** (once). In the repository go to **Settings → Pages → Build and
   deployment**. Set **Source** to **Deploy from a branch**, pick the branch that holds this
   folder (`claude/amazing-faraday-wi6lf3`, or `main` once merged) and the folder **/docs**,
   then **Save**. About a minute later the site is live at
   `https://aumpatel11.github.io/AumPatel11/`.
2. **Register a free domain** at DigitalPlat (https://dash.domain.digitalplat.org/). The
   free endings are `.dpdns.org`, `.us.kg`, `.qzz.io`, `.xx.kg` and `.qd.je`, with one domain
   per account, for example `aumpatel.qzz.io`.
3. **Point it at Cloudflare.** DigitalPlat has no DNS record editor, so add the domain to a
   free Cloudflare account. Cloudflare shows two nameservers: enter both in the domain's
   nameserver fields in the DigitalPlat dashboard.
4. **Add the DNS record** in Cloudflare: type `CNAME`, name `@`, target
   `aumpatel11.github.io`, proxy status **DNS only** (grey cloud).
5. **Connect the domain.** Back in GitHub **Settings → Pages**, type the domain under
   **Custom domain** and **Save**. When the DNS check passes (minutes to a few hours), tick
   **Enforce HTTPS**. GitHub adds a `CNAME` file to this folder for you.

The brief suggests Wix or WordPress; check with your lecturer that a custom site is
acceptable before you submit.

## Files

```
docs/
├── index.html            all page content
├── .nojekyll             publish the files as they are on GitHub Pages
├── assets/img/           portrait and LinkedIn card photo
├── assets/css/styles.css design tokens (light and dark), layout and components
└── assets/js/
    ├── main.js           theme, navigation, scrolling, reader, form, contour panels
    ├── hero-map.js       three.js 3D contour map in the hero
    └── terrain.js        shared Auckland height field and 2D contour renderer
```

Libraries load from public CDNs, pinned to exact versions: three.js 0.160.0, GSAP 3.12.5
(with ScrollTrigger) and Lenis 1.1.13. Fonts are Archivo, Newsreader and Martian Mono
from Google Fonts.
