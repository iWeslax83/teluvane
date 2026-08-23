# Component Marketplaces, KokonutUI, Skiper UI, Aceternity UI

## What they are
Three shadcn-compatible, Tailwind + Motion component catalogs, merged into one entry because they overlap heavily in visual vocabulary and installation model (CLI-installable components):

- **KokonutUI** (kokonutui.com), free/open-source. Glass-effect music-player and file-upload widgets with motion-driven micro-interactions.
- **Skiper UI** (skiper-ui.com), paid ($129–$549, 106+ components). Oriented around high-craft micro-interaction detail (image reveals, cursor trails, dynamic-island patterns, token-swap UI), explicitly inspired by "Devouring Details" style craft.
- **Aceternity UI** (ui.aceternity.com), free/paid. Landing-page effects: 3D card/pin effects, aurora/wavy/lamp gradient backgrounds, parallax, canvas interactions, text reveals.

## What to extract
- Named interaction *concepts* worth recognizing (image reveal on hover, cursor trail, 3D tilt card, token-swap transition) rather than literal code, treat these as a vocabulary of interaction ideas, not a component you paste in.
- Skiper UI's premium tier and detail is paywalled; only the free/documented parts are usable as a citable reference.

## CONFLICT WARNING, do not copy visual style directly
Aceternity UI in particular relies heavily on **gradient backgrounds, glow effects, and glassmorphism** (aurora/wavy/lamp effects, glass panels). These directly violate this user's global CLAUDE.md design rule: "No gradients, no glassmorphism, no purple. Use a flat background color plus exactly ONE accent color. Solid fills only."

When drawing on this reference: extract the *interaction idea* (e.g. "a card that tilts in 3D on hover") and re-implement it with a flat background and the project's single accent color, never copy the gradient/glass visual treatment wholesale.

## When to use this
Reach for this when the task needs a specific micro-interaction idea (hover reveal, drag-to-reorder, animated tab indicator) and you need a name/example for it, not when picking overall page style.

## Caveats
Skiper UI premium components are paywalled. Aceternity UI's decorative style conflicts with existing design rules, see conflict warning above.
