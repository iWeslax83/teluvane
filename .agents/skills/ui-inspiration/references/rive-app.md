# rive.app, Interactive Vector Animation Reference

## What it is
Design/runtime tool for interactive vector animations (state-machine-driven), plus its site and community showcase. A reference for *interactive, state-driven* motion, distinct from scroll or timeline animation.

## What to extract
- **State machines over linear timelines**: model an animated element's behavior as states and transitions (idle, hover, active, loading) driven by real app state, not a single fixed-length clip.
- **Input-reactive motion**: animations that respond continuously to input (pointer position, drag, scroll value) rather than only firing discrete triggers.
- **Vector-based, not video**: interactive animations authored as vectors stay crisp at any size and are far lighter than a Lottie/video loop for the same effect.
- **Small, purposeful interactive assets**: icons, mascots, or illustrations that react to user action carry real information (loading state, success/error), not decoration for its own sake.

## When to use this
Reach for this when a UI needs a small interactive asset that reacts to real state (an icon, illustration, or loader with meaningful states), not for full-page composition or scroll choreography.

## Caveats
Runtime interactive vector assets require the Rive runtime/player and authored `.riv` files, this is a heavier dependency than CSS/SVG animation, only reach for it when the state-driven interactivity is actually needed.
