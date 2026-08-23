// frontend/components/blog/ArticleLayout.tsx
import Link from "next/link";
import { BG, INK, ACCENT, MUTED, BORDER } from "@/lib/landingTheme";

export const proseStyles = {
  h2: { fontSize: "1.35rem", fontWeight: 800, letterSpacing: "-.015em", margin: "2.2rem 0 .8rem", color: INK },
  p: { fontSize: "1rem", color: INK, lineHeight: 1.7, marginBottom: "1.1rem" },
  li: { fontSize: "1rem", color: INK, lineHeight: 1.7, marginBottom: ".5rem" },
};

export default function ArticleLayout({
  title,
  description,
  date,
  children,
}: {
  title: string;
  description: string;
  date: string;
  children: React.ReactNode;
}) {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: BG, color: INK, minHeight: "100dvh", lineHeight: 1.6 }}>
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "4rem 1.5rem 6rem" }}>
        <Link href="/blog" className="landing-link" style={{ color: ACCENT, fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>
          &larr; Back to blog
        </Link>
        <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, margin: "1.6rem 0 .6rem" }}>
          {date}
        </div>
        <h1 style={{ fontSize: "clamp(1.9rem, 4.5vw, 2.5rem)", fontWeight: 900, letterSpacing: "-.03em", lineHeight: 1.15, marginBottom: "1rem" }}>
          {title}
        </h1>
        <p style={{ fontSize: "1.1rem", color: MUTED, marginBottom: "2.5rem" }}>{description}</p>

        <article>{children}</article>

        <div style={{ marginTop: "3rem", paddingTop: "1.5rem", borderTop: `1px solid ${BORDER}`, fontSize: ".82rem", color: MUTED }}>
          Not legal advice. TELUVANE is a technical tool, consult qualified counsel for regulatory guidance.
        </div>

        <div style={{ marginTop: "2.5rem", padding: "1.8rem", background: "transparent", border: `1px solid ${BORDER}`, borderLeft: `3px solid ${ACCENT}`, borderRadius: 6 }}>
          <div style={{ fontWeight: 700, marginBottom: ".4rem" }}>Want to see the log yourself?</div>
          <p style={{ fontSize: ".9rem", color: MUTED, marginBottom: "1rem" }}>
            TELUVANE hash-chains every AI agent action and audits it against EU AI Act, ISO 42001, NIST AI RMF, and SOC 2 policy packs.
          </p>
          <div style={{ display: "flex", gap: ".75rem", flexWrap: "wrap" }}>
            <Link href="/login" className="landing-btn" style={{ display: "inline-flex", padding: ".6rem 1.2rem", borderRadius: 7, fontSize: ".9rem", fontWeight: 700, background: ACCENT, color: "#ffffff", textDecoration: "none" }}>
              Get started free
            </Link>
            <a href="https://github.com/iWeslax83/teluvane" target="_blank" rel="noopener" className="landing-btn landing-link" style={{ display: "inline-flex", padding: ".6rem 1.2rem", borderRadius: 7, fontSize: ".9rem", fontWeight: 600, background: "transparent", color: INK, border: `1.5px solid ${BORDER}`, textDecoration: "none" }}>
              View on GitHub
            </a>
          </div>
        </div>
      </div>
    </main>
  );
}
