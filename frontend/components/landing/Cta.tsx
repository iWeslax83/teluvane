import { BG, INK, MUTED } from "@/lib/landingTheme";

export default function Cta() {
  return (
    <section id="cta" style={{ padding: "clamp(3rem, 7vw, 5rem) 1.25rem", background: BG }}>
      <div style={{ maxWidth: 560, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: "clamp(1.6rem, 4vw, 2rem)", fontWeight: 800, letterSpacing: "-.02em", marginBottom: ".8rem", color: INK }}>
          Start recording in minutes
        </h2>
        <p style={{ fontSize: "1rem", color: MUTED, marginBottom: "1.6rem" }}>
          No credit card required. The free plan includes the dashboard, API keys and HTML evidence packs.
        </p>
        <a href="/login" className="landing-btn landing-btn-primary" style={{
          display: "inline-block",
          padding: ".8rem 2rem", borderRadius: 8,
          fontSize: "1rem", fontWeight: 700, textDecoration: "none",
        }}>
          Get started free
        </a>
      </div>
    </section>
  );
}
