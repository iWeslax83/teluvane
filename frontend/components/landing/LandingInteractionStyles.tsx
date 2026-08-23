// frontend/components/landing/LandingInteractionStyles.tsx
import { ACCENT, ACCENT_DARK, ACCENT_ON_FILL, INK, BG, BORDER, EASE } from "@/lib/landingTheme";

export default function LandingInteractionStyles() {
  return (
    <style>{`
      .landing-btn {
        transition: transform 100ms ease-out, background-color 160ms ${EASE}, color 160ms ${EASE}, border-color 160ms ${EASE};
      }
      .landing-btn:active {
        transform: scale(0.97);
      }
      .landing-btn:focus-visible {
        outline: 2px solid ${ACCENT};
        outline-offset: 3px;
      }
      /* Filled action: commits to the accent, deepens on hover. */
      .landing-btn-primary {
        background: ${ACCENT};
        color: ${ACCENT_ON_FILL};
        border: 1.5px solid transparent;
      }
      .landing-btn-primary:hover {
        background: ${ACCENT_DARK};
      }
      /* Outline action: earns full presence on hover instead of a flat tint. */
      .landing-btn-ghost {
        background: transparent;
        color: ${INK};
        border: 1.5px solid ${BORDER};
      }
      .landing-btn-ghost:hover {
        background: ${INK};
        color: ${BG};
        border-color: ${INK};
      }
      .landing-link:focus-visible {
        outline: 2px solid ${ACCENT};
        outline-offset: 2px;
        border-radius: 2px;
      }
    `}</style>
  );
}
