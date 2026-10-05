// Shared with app/globals.css :root — landing page uses the same brand tokens as the
// dashboard, auth flows, and legal pages so the identity doesn't reset at the login wall.
export const BG = "#f4efe6";
export const SURFACE = "#fbf8f1";
export const INK = "#1a1714";
export const ACCENT = "#2f5266";
export const ACCENT_DARK = "#213a49";
export const ACCENT_ON_FILL = "#ffffff";
// 5.1:1 on BG (WCAG AA for body text). The old #8a8275 was about 3.4:1.
export const MUTED = "#6b6458";
export const BORDER = "#e3dccd";
// Semantic critical/alert color, separate from ACCENT. Used only where something
// is actually wrong (a broken hash chain, a tampered event), never as decoration.
export const CRITICAL = "#c01c28";
// Shared interaction curve for landing hover/press transitions (ease-out-expo
// family) so every interactive element settles the same way, instead of each
// component picking its own timing function.
export const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
