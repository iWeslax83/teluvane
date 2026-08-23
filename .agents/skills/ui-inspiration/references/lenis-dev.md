# lenis.dev, Smooth Scroll Reference

## What it is
Documentation/demo site for Lenis, the widely-used smooth-scroll library. A reference for scroll *feel*, not a visual gallery.

## What to extract
- **Inertia-based scroll damping**: replace native abrupt scroll with eased/lerped scroll position so movement decelerates naturally instead of stopping instantly.
- **Consistent scroll behavior across input methods**: wheel, trackpad, and touch should all feel governed by the same easing curve.
- **Sync with scroll-linked animation**: Lenis exposes scroll progress that scroll-triggered animations (e.g. via GSAP ScrollTrigger or similar) should read from directly, keeps animation and scroll position from drifting apart.
- **Restraint on duration**: too much damping reads as laggy/unresponsive, tune lerp/duration values conservatively and test with real trackpad input.

## When to use this
Reach for this when a page's animations feel disconnected from native scroll, or when scroll itself should feel more deliberate/premium rather than instant.

## Caveats
Smooth-scroll libraries can break native browser scroll behaviors (anchor links, scroll-to-text, accessibility tools) if not configured carefully, verify keyboard and screen-reader scroll still work.
