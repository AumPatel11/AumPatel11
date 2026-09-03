---
name: ui-design-review
description: Critique an interface - layout, hierarchy, spacing, typography, states, and copy - and return specific fixes. Use when asked to review, improve, polish, or give feedback on a screen, page, or component design.
---

# UI design review

Lead with what is wrong. A review that opens with praise buries the useful part.

## What to check

**Hierarchy.** Can you tell in one second what the screen is for and what the
primary action is? If two elements compete for that role, one of them is wrong.

**Spacing.** Values should come from one scale. Related things sit closer than
unrelated things. Inconsistent gaps read as bugs even when nothing is broken.

**Typography.** Three sizes and two weights carry most interfaces. Body text runs
45-75 characters per line. Line height rises as size falls.

**Alignment.** Everything sits on a shared grid or edge. A single element off the
grid is the one people notice.

**Color.** Neutral by default, color for meaning. Every color used for status
needs a non-color partner.

**States.** Empty, loading, error, and too-much-content states exist and are
designed, not left to the default. Most reviews find these missing.

**Copy.** Buttons name the action they perform, not "Submit" or "OK". Error text
says what to do next, not what went wrong internally.

## How to report

For each finding write one sentence on the problem and one on the fix. Order by
impact. Cap the list at what someone can act on in a sitting - roughly seven items.
Say plainly when something already works well, but only where you can name why.
