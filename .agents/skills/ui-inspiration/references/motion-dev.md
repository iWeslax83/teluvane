# motion.dev, Motion Principles Reference

## What it is
Official documentation for Motion (formerly Framer Motion), a JavaScript/React animation library. Not a visual gallery or component catalog, a reference for animation *mechanics and philosophy*.

## What to extract
- **Spring physics over eased curves**: prefer spring-based transitions (mass/stiffness/damping) for natural-feeling motion instead of hand-tuned cubic-bezier easing.
- **Independent transform composition**: animate `x`, `y`, `scale`, `rotate` etc. as independent values without nesting wrapper `<div>`s per transform.
- **Native gesture handling**: hover/press/drag/in-view states should be handled by the animation layer's built-in gesture system, not bolted-on manual event listeners.
- **Orchestration**: use variants, stagger, and timelines to sequence multiple elements instead of manually chaining timeouts.
- **Performance budget**: Motion's own "MotionScore" concept frames animation as something with a measurable performance cost, treat animation choices as a budget, not a free decoration.

## When to use this
Reach for this when deciding *how* something should move: timing, easing, sequencing, gesture response. This is not a source for what a component should look like.

## Caveats
None, official docs, freely accessible, no paywall.
