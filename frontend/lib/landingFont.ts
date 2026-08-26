// Landing-scoped typeface: the rest of the app (dashboard, auth, legal pages)
// keeps the serif stack from globals.css. Only the landing page opts into a
// real chosen sans so headings and body read as "security infra," not editorial.
// Public Sans (USWDS, the US federal design system's typeface) fits a
// compliance/regulatory product better than a generic startup sans, and its
// variable weight axis covers the full 100-900 range already used in the
// landing components without capping anything down.
import { Public_Sans, IBM_Plex_Mono } from "next/font/google";

export const landingSans = Public_Sans({ subsets: ["latin"], weight: "variable", display: "swap" });
export const landingMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600", "700"], display: "swap" });
