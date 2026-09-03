---
name: ui-components
description: Build React or plain-HTML interface components that match an existing codebase. Use when asked to create, restyle, or refactor a button, form, modal, table, card, nav, or any other reusable UI element.
---

# UI components

## Before writing anything

1. Find a sibling component of the same kind and read it end to end. Match its
   file layout, prop naming, and styling mechanism instead of introducing a new one.
2. Identify how the project handles styling: CSS modules, Tailwind, styled
   components, or plain stylesheets. Never mix two systems in one component.
3. Check for an existing primitive. A second `Button` is a bug, not a feature.

## Structure

- One component per file, named the same as the file.
- Props are typed. In TypeScript projects that means an exported interface; in
  JavaScript projects match whatever the neighbours use.
- Keep state as local as it can be. Lift it only when a second component reads it.
- Accept and forward `className` and `...rest` on the root element so callers can
  extend the component without forking it.

## Styling rules

- Use the project's design tokens for color, spacing, and radius. A raw hex value
  in a component is a defect unless the file already contains them.
- Size with relative units and let the container decide the width.
- Every interactive element needs visible `:hover`, `:focus-visible`, and
  `:disabled` states. Focus rings are never removed without a replacement.
- Support both color schemes if the project does. Define light values first, then
  override under the dark selector the project already uses.

## Before you call it done

- Render it with the longest realistic content, not "Lorem ipsum".
- Check the empty, loading, and error states exist if the component fetches.
- Tab through it with the keyboard.
