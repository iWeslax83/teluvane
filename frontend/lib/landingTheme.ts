// Shared with app/globals.css :root — landing page uses the same brand tokens as the
// dashboard, auth flows, and legal pages so the identity doesn't reset at the login wall.
export const BG = "#f4efe6";
export const SURFACE = "#fbf8f1";
export const INK = "#1a1714";
export const ACCENT = "#b4451f";
export const ACCENT_DARK = "#9d3b18";
export const ACCENT_ON_FILL = "#ffffff";
export const MUTED = "#8a8275";
export const BORDER = "#e3dccd";
// Shared interaction curve for landing hover/press transitions (ease-out-expo
// family) so every interactive element settles the same way, instead of each
// component picking its own timing function.
export const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
