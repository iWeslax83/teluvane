// frontend/app/about/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import JsonLd from "@/components/JsonLd";
import { siteUrl, FOUNDER } from "@/lib/site";
import { BG, INK, ACCENT, MUTED, BORDER } from "@/lib/landingTheme";

export const metadata: Metadata = {
  title: "About TELUVANE and its founder, Emir Sakarya",
  description:
    "TELUVANE is built by Emir Sakarya in Bursa, Türkiye. Why it exists, who builds it, and where to find the code.",
  alternates: { canonical: "/about" },
  openGraph: {
    type: "profile",
    title: "About TELUVANE and its founder, Emir Sakarya",
    url: "/about",
  },
};

const personLd = {
  "@context": "https://schema.org",
  "@type": "Person",
  "@id": `${siteUrl}/about#emir-sakarya`,
  name: FOUNDER.name,
  url: `${siteUrl}/about`,
  jobTitle: "Founder",
  homeLocation: { "@type": "Place", address: { "@type": "PostalAddress", addressLocality: "Bursa", addressCountry: "TR" } },
  worksFor: [
    { "@id": `${siteUrl}/#organization` },
    { "@type": "Organization", name: "Stratos UAV", url: FOUNDER.stratos },
  ],
  sameAs: [FOUNDER.linkedin, FOUNDER.github, FOUNDER.stratos],
};

const p = { fontSize: "1rem", color: INK, lineHeight: 1.7, marginBottom: "1.1rem" } as const;
const h2 = { fontSize: "1.35rem", fontWeight: 800, letterSpacing: "-.015em", margin: "2.2rem 0 .8rem", color: INK } as const;
const link = { color: ACCENT, fontWeight: 600 } as const;

export default function AboutPage() {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: BG, color: INK, minHeight: "100dvh", lineHeight: 1.6 }}>
      <JsonLd data={personLd} />
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "4rem 1.5rem 6rem" }}>
        <Link href="/" className="landing-link" style={{ color: ACCENT, fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>
          &larr; Back to homepage
        </Link>
        <h1 style={{ fontSize: "clamp(1.9rem, 4.5vw, 2.5rem)", fontWeight: 900, letterSpacing: "-.03em", lineHeight: 1.15, margin: "1.6rem 0 1rem" }}>
          About TELUVANE
        </h1>
        <p style={{ fontSize: "1.1rem", color: MUTED, marginBottom: "2rem" }}>
          TELUVANE records what AI agents do and checks it against compliance frameworks, so a team can show an auditor what actually happened.
        </p>

        <h2 style={h2}>What it does</h2>
        <p style={p}>
          Every LLM call, tool call, and tool result is stored in a SHA-256 hash chain per session, so editing a stored row breaks the chain visibly. A tribunal then audits the session against EU AI Act, ISO 42001, NIST AI RMF, and SOC 2 policy packs and returns verdicts with citations. Sessions can optionally be anchored on Avalanche and checked on the public <Link href="/verify" style={link}>verification page</Link>.
        </p>

        <h2 style={h2}>Who builds it</h2>
        <p style={p}>
          TELUVANE is founded and built by {FOUNDER.name}, an engineer in Bursa, Türkiye. {FOUNDER.name} also founded <a href={FOUNDER.stratos} rel="noopener" style={link}>Stratos UAV</a>, a student engineering team building autonomous aircraft, and was part of the team that placed first in Turkey at the NASA Space Apps Challenge 2025.
        </p>

        <h2 style={h2}>Find us</h2>
        <ul style={{ paddingLeft: "1.2rem", margin: 0 }}>
          <li style={p}><a href={FOUNDER.github + "/teluvane"} rel="noopener" style={link}>Source code on GitHub</a></li>
          <li style={p}><a href={FOUNDER.linkedin} rel="noopener" style={link}>{FOUNDER.name} on LinkedIn</a></li>
          <li style={p}><a href="mailto:hello@teluvane.com" style={link}>hello@teluvane.com</a></li>
        </ul>

        <div style={{ marginTop: "3rem", paddingTop: "1.5rem", borderTop: `1px solid ${BORDER}`, fontSize: ".82rem", color: MUTED }}>
          Not legal advice. TELUVANE is a technical tool, consult qualified counsel for regulatory guidance.
        </div>
      </div>
    </main>
  );
}
