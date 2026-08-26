// Landing-scoped typeface: the rest of the app (dashboard, auth, legal pages)
// keeps the serif stack from globals.css. Only the landing page opts into a
// real chosen sans so headings and body read as "security infra," not editorial.
import { Geist } from "next/font/google";

export const geistSans = Geist({ subsets: ["latin"], display: "swap" });
