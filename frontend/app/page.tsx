// frontend/app/page.tsx
import type { Metadata } from "next";
import LandingBody from "@/components/landing/LandingBody";
import BrandMark from "@/components/BrandMark";
import { INK, ACCENT, ACCENT_ON_FILL } from "@/lib/landingTheme";
import { geistSans } from "@/lib/landingFont";

export const metadata: Metadata = {
  title: "TELUVANE: AI Agent Accountability",
  description: "Tamper-evident flight recorder and autonomous compliance tribunal for AI agents. Prove what your AI agents did, before a regulator asks.",
};

export default function Landing() {
  return (
    <div className={geistSans.className}>
      <nav className="landing-nav">
        <a href="#opening" className="brand landing-link" style={{ color: INK, textDecoration: "none" }}>
          <span className="mark"><BrandMark /></span> TELUVANE
        </a>
        <ul className="landing-nav-links">
          <li><a href="#how" className="landing-link" style={{ color: INK, fontSize: ".9rem", fontWeight: 500, textDecoration: "none" }}>How it works</a></li>
          <li><a href="#pricing" className="landing-link" style={{ color: INK, fontSize: ".9rem", fontWeight: 500, textDecoration: "none" }}>Pricing</a></li>
          <li>
            <a href="/login" className="landing-btn" style={{
              background: ACCENT, color: ACCENT_ON_FILL,
              padding: ".38rem .9rem", borderRadius: 6, fontSize: ".9rem", fontWeight: 700,
              textDecoration: "none",
            }}>Get started free</a>
          </li>
        </ul>
      </nav>

      <LandingBody />
    </div>
  );
}
