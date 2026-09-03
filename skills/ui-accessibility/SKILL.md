---
name: ui-accessibility
description: Audit or fix the accessibility of a page or component - keyboard traps, missing labels, contrast, focus order, screen reader semantics. Use when asked about a11y, WCAG, screen readers, keyboard navigation, or ARIA.
---

# UI accessibility

Work in this order. The earlier items break more users than the later ones.

## 1. Semantics before ARIA

Use the element that already means what you want: `button` for actions, `a[href]`
for navigation, `label` bound to its input, `h1`-`h6` in order, `ul`/`ol` for lists.
ARIA is a patch for gaps in HTML, not a substitute. A `div` with `role="button"`
needs key handlers, a tab index, and a disabled state you now maintain by hand.

## 2. Keyboard

- Every interactive element must be reachable with Tab and operable with Enter or Space.
- Focus order follows visual order. Positive `tabindex` values break this - remove them.
- Dialogs trap focus while open, restore it to the trigger on close, and close on Escape.
- `:focus-visible` must be visible against the background it sits on.

## 3. Names and state

- Every control has an accessible name: visible text, `aria-label`, or a bound `label`.
- Icon-only buttons carry a name; decorative icons are `aria-hidden="true"`.
- Images need `alt`. Decorative images take `alt=""`, never a missing attribute.
- Communicate state with `aria-expanded`, `aria-selected`, `aria-current`, and
  `aria-invalid` rather than color alone.

## 4. Contrast and motion

- Body text needs 4.5:1 against its background. Large text and UI borders need 3:1.
- Never encode meaning in color alone. Add an icon, a label, or a pattern.
- Respect `prefers-reduced-motion` for anything that moves more than a fade.

## Reporting an audit

Give each finding as: the element, what breaks, which user it breaks for, and the
fix. Rank by severity, not by file order. Do not pad the list with passing checks.
