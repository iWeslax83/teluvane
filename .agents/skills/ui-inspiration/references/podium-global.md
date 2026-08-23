# podium.global, Sequence-Driven Animation Reference

## What it is
Agency portfolio site built around scroll- and sequence-driven animation, sections choreographed as a timed narrative rather than isolated hover effects. A composition reference, not a component catalog.

## What to extract
- **Scene-based sequencing**: treat a scroll pass as a series of scenes with a beginning, hold, and exit state, not a stream of independent fade-ins.
- **Scroll-linked progress, not scroll-triggered snapshots**: tie animation progress directly to scroll position (like a scrubbed timeline) instead of firing a one-shot animation when an element enters the viewport.
- **Pinning for emphasis**: pin a section in place while its internal content animates through multiple states, reserve this for a handful of key moments, not every section.
- **Choreographed exits**: give elements a deliberate exit transition tied to the next scene entering, not just an entrance animation.

## When to use this
Reach for this when a page needs a strong narrative arc across scroll, portfolio/case-study pages, product story sections, anything meant to feel directed rather than a stack of cards.

## Caveats
Heavy use of pinning/scrubbing can hurt scroll feel on lower-end devices and mobile, use sparingly and test real scroll performance before shipping.
