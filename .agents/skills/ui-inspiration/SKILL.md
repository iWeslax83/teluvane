---
name: ui-inspiration
description: Curated design-inspiration reference for UI/UX work, routes to distilled notes on motion.dev (motion principles), styles.refero.design (real product design systems), Godly (whole-page composition galleries), Mobbin (production screenshots), shadcn-style component marketplaces, podium.global (sequence-driven animation), lenis.dev (smooth scroll), and rive.app (interactive vector animation). Use when designing or redesigning UI, choosing animation behavior, picking page composition, or looking for a named interaction pattern. Not a substitute for the project's own design rules (e.g. CLAUDE.md), cross-check anything pulled from here against those before using it.
---

# UI Inspiration

A router to curated, distilled design-reference sources. Each source below covers different ground; pick based on the specific question, not "just open all of them."

## Decision guide

| Question | Reference |
|---|---|
| How should this animate, timing, physics, gestures? | `references/motion-dev.md` |
| What should this look like if it should feel like [a real product]? | `references/refero-styles.md` |
| What's the overall shape/flow of this landing page? | `references/godly.md` |
| How do real production apps handle this specific flow? | `references/mobbin.md` |
| I need a named micro-interaction idea (hover reveal, 3D tilt, etc.) | `references/component-marketplaces.md` |
| How should a page choreograph scroll into a narrative sequence? | `references/podium-global.md` |
| How should scroll itself feel (damping, inertia)? | `references/lenis-dev.md` |
| I need a small interactive vector asset (icon/illustration with states) | `references/rive-app.md` |

## Required cross-check

Before applying anything pulled from these references, check it against this project's own design rules (e.g. a global or project `CLAUDE.md`). These references are inspiration sources, not an override, several of them (especially `component-marketplaces.md`) showcase patterns like gradients and glassmorphism that are explicitly banned in this user's design rules. When a reference and an existing design rule conflict, the design rule wins; extract the underlying idea and re-implement it within the rule, don't copy the reference's literal visual treatment.

## Deliberately excluded sources

React Bits, MotionSites AI, bklit.com, motion-primitives.com, and tasteskill.dev were evaluated and excluded: the first four for thin/unverified/redundant content, and tasteskill.dev because it's an AI-agent instruction package (functionally overlapping with this user's own CLAUDE.md), not a design-inspiration source.
