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

## Live site

**https://aumpatel.up.railway.app**

Railway (project `aum-eportfolio`, service `eportfolio`) serves this `/docs` folder as static
files with Caddy. It rebuilds by itself on every push to `claude/amazing-faraday-wi6lf3` that
changes something in `/docs`. The service sleeps when nobody is visiting, so it uses almost
none of the Railway plan's monthly usage; the first visit after a quiet spell takes a second
or two longer to open.

## Contact form: one click to switch on

Messages from the contact form go to **aumpatel987@gmail.com** through
[FormSubmit](https://formsubmit.co) (free, no account). The address is set in
`data-endpoint` on `<form id="contact-form">`.

1. Open the live site and send yourself a test message from the form.
2. FormSubmit emails aumpatel987@gmail.com a message with an **Activate Form** button.
   Select it once (check the spam folder if it isn't in the inbox).
3. From then on, every message arrives in your inbox, and replying answers the sender.

Until it's activated, or whenever sending fails, the form gives the visitor a ready-made
email to send instead, so no message is lost.

## Updating your details

Everything on the page is in `index.html`.

- **Links to the work**: the "See the work live" list at the end of the project section,
  the button on each case study and the CV's project entries link to ovenfreshbakery.uk,
  the AussieStitch shop and uncheckdoc.com. When AussieStitch moves to its own domain,
  replace `aussiestitch-production-1cbd.up.railway.app` everywhere it appears.
- **LinkedIn**: linked to linkedin.com/in/aum-patel-95086b356 in the LinkedIn card, the
  contact section, the CV and the footer.
- **Email**: aumpatel987@gmail.com in the contact section, the CV, the footer and the form.
- **Reflections**: each journal card has a title, a one-line excerpt and a hidden
  `entry__full` block with three headings (What I learned, Why it was useful, How I'm
  applying it). Aim for 200–350 words per post. Reading time is calculated automatically.
- **Placeholders**: none are left. If you add text wrapped in `<span class="ph">[...]</span>`,
  it shows with a red dashed underline and a counter in the corner until you replace it.

## Previewing locally

Any static server works, for example:

```bash
cd docs && python3 -m http.server 8000
```

Then open http://localhost:8000. Opening `index.html` straight from the file system will not
load the scripts, because browsers block ES modules on `file://` URLs.

## A free custom domain (optional)

The Railway address works as it is. To use a free domain of your own as well:

1. **Register it** at DigitalPlat (https://dash.domain.digitalplat.org/). The free endings
   are `.dpdns.org`, `.us.kg`, `.qzz.io`, `.xx.kg` and `.qd.je`, with one domain per account,
   for example `aumpatel.qzz.io`. DigitalPlat asks for your own name and contact details,
   so only you can do this step.
2. **Point it at Cloudflare.** DigitalPlat has no DNS record editor, so add the domain to a
   free Cloudflare account. Cloudflare shows two nameservers: enter both in the domain's
   nameserver fields in the DigitalPlat dashboard.
3. **Add it in Railway.** In the `eportfolio` service go to **Settings → Networking →
   Custom Domain** and type the domain. Railway shows a `CNAME` record and a `TXT` record.
4. **Add both records in Cloudflare**, with proxy status **DNS only** (grey cloud). Railway
   checks them and issues the HTTPS certificate by itself, usually within an hour.

## Alternative: GitHub Pages

The folder also works on GitHub Pages unchanged (`.nojekyll` tells Pages to publish the
files as they are). In the repository go to **Settings → Pages**, set **Source** to **Deploy
from a branch**, pick `claude/amazing-faraday-wi6lf3` and the folder **/docs**, and **Save**.
The site then also appears at `https://aumpatel11.github.io/AumPatel11/`.

The brief suggests Wix or WordPress; check with your lecturer that a custom site is
acceptable before you submit.

## Files

```
docs/
├── index.html            all page content
├── .nojekyll             publish the files as they are on GitHub Pages
├── assets/img/           portrait, LinkedIn card photo and link preview (og.jpg)
├── assets/css/styles.css design tokens (light and dark), layout and components
└── assets/js/
    ├── main.js           theme, navigation, scrolling, reader, form, contour panels
    ├── hero-map.js       three.js 3D contour map in the hero
    └── terrain.js        shared Auckland height field and 2D contour renderer
```

Libraries load from public CDNs, pinned to exact versions: three.js 0.160.0, GSAP 3.12.5
(with ScrollTrigger) and Lenis 1.1.13. Fonts are Archivo, Newsreader and Martian Mono
from Google Fonts.
