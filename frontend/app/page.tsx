// frontend/app/page.tsx
import type { Metadata } from "next";
import LandingBody from "@/components/landing/LandingBody";
import BrandMark from "@/components/BrandMark";
import { INK, ACCENT, ACCENT_ON_FILL } from "@/lib/landingTheme";
import { landingSans } from "@/lib/landingFont";
import JsonLd from "@/components/JsonLd";
import { siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "TELUVANE: AI Agent Accountability",
  description: "Tamper-evident flight recorder and autonomous compliance tribunal for AI agents. Prove what your AI agents did, before a regulator asks.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "TELUVANE: AI Agent Accountability",
    description: "Tamper-evident flight recorder and autonomous compliance tribunal for AI agents.",
    url: "/",
  },
};

const softwareLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "@id": `${siteUrl}/#software`,
  name: "TELUVANE",
  url: siteUrl,
  applicationCategory: "SecurityApplication",
  operatingSystem: "Web",
  description:
    "Records every LLM call, tool call, and tool result an AI agent makes into a SHA-256 hash-chained log, then audits sessions against EU AI Act, ISO 42001, NIST AI RMF, and SOC 2 policy packs.",
  publisher: { "@id": `${siteUrl}/#organization` },
  offers: [
    { "@type": "Offer", name: "Free", price: "0", priceCurrency: "USD" },
    { "@type": "Offer", name: "Starter", price: "9.99", priceCurrency: "USD", priceSpecification: { "@type": "UnitPriceSpecification", price: "9.99", priceCurrency: "USD", billingDuration: "P1M" } },
    { "@type": "Offer", name: "Pro", price: "19.99", priceCurrency: "USD", priceSpecification: { "@type": "UnitPriceSpecification", price: "19.99", priceCurrency: "USD", billingDuration: "P1M" } },
  ],
};

export default function Landing() {
  return (
    <div className={landingSans.className}>
      <JsonLd data={softwareLd} />
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
