import { BG, INK, MUTED, BORDER } from "@/lib/landingTheme";

const LINKS = [
  { href: "mailto:hello@teluvane.com", label: "Contact" },
  { href: "/about", label: "About" },
  { href: "/blog", label: "Blog" },
  { href: "/login", label: "Dashboard" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/accessibility", label: "Accessibility" },
];

export default function Footer() {
  return (
    <footer className="site-footer" style={{ background: BG, color: MUTED, padding: "2rem 1.25rem", textAlign: "center", fontSize: ".83rem", borderTop: `1px solid ${BORDER}` }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: ".75rem" }}>
        <div><strong style={{ color: INK }}>TELUVANE</strong>: AI Agent Accountability and Compliance</div>
        <nav aria-label="Footer" style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: ".25rem 1.25rem" }}>
          {LINKS.map(({ href, label }) => (
            <a key={href} href={href} className="landing-link" style={{ color: MUTED, textDecoration: "none", padding: ".4rem 0" }}>{label}</a>
          ))}
        </nav>
        <div style={{ fontSize: ".78rem", color: MUTED }}>
          Bursa, Türkiye
        </div>
        <div style={{ fontSize: ".78rem", color: MUTED }}>
          Not legal advice. TELUVANE is a technical tool, consult qualified counsel for regulatory guidance.
        </div>
      </div>
    </footer>
  );
}
