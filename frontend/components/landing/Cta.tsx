import { BG, SURFACE, INK, ACCENT, MUTED, BORDER } from "@/lib/landingTheme";

export default function Cta() {
  return (
    <section id="cta" style={{ padding: "5rem 2rem", background: BG }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <div style={{ fontSize: ".75rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: ".6rem", textAlign: "center" }}>Early access</div>
        <h2 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-.02em", marginBottom: "1rem", color: INK, textAlign: "center" }}>Get started today</h2>
        <p style={{ fontSize: "1.05rem", color: MUTED, textAlign: "center", maxWidth: 520, margin: "0 auto" }}>
          We&apos;re onboarding early teams. Create your account and start monitoring your agents in minutes.
        </p>
        <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 14, padding: "2.8rem", maxWidth: 520, margin: "2.5rem auto 0", boxShadow: "0 2px 12px rgba(0,0,0,.15)", textAlign: "center" }}>
          <h3 style={{ fontSize: "1.4rem", fontWeight: 800, marginBottom: ".5rem", color: INK }}>Start for free</h3>
          <p style={{ color: MUTED, fontSize: ".9rem", marginBottom: "1.4rem" }}>
            No credit card required. Full access to the dashboard, API key management, and audit reports.
          </p>
          <a href="/login" className="landing-btn landing-btn-primary" style={{
            display: "inline-block",
            padding: ".75rem 2rem", borderRadius: 8,
            fontSize: "1rem", fontWeight: 700, textDecoration: "none",
          }}>
            Get started free →
          </a>
        </div>
      </div>
    </section>
  );
}
