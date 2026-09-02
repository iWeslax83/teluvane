import { BG, SURFACE, BORDER, ACCENT, ACCENT_ON_FILL, INK, MUTED } from "@/lib/landingTheme";

function Tier({
  eyebrow, price, priceSuffix, description, features, ctaLabel, ctaHref, emphasized,
}: {
  eyebrow: string; price: string; priceSuffix?: string; description: string;
  features: string[]; ctaLabel: string; ctaHref: string; emphasized?: boolean;
}) {
  return (
    <div style={{
      flex: "1 1 280px",
      minWidth: 0,
      background: emphasized ? BG : SURFACE,
      border: `1.5px solid ${emphasized ? ACCENT : BORDER}`,
      borderRadius: 12,
      padding: "2rem 1.7rem",
      position: "relative",
      transform: emphasized ? "translateY(-.6rem)" : undefined,
    }}>
      {emphasized && (
        <div style={{
          position: "absolute", top: 0, left: "1.7rem", transform: "translateY(-50%)",
          background: ACCENT, color: ACCENT_ON_FILL,
          fontSize: ".7rem", fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase",
          padding: ".2rem .6rem", borderRadius: 3,
        }}>
          Most teams pick this
        </div>
      )}
      <div style={{ fontSize: ".78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".07em", color: emphasized ? ACCENT : MUTED, marginBottom: ".5rem", marginTop: emphasized ? ".3rem" : 0 }}>
        {eyebrow}
      </div>
      <div style={{ fontSize: "2.4rem", fontWeight: 900, letterSpacing: "-.03em", color: INK, fontVariantNumeric: "tabular-nums" }}>
        {price}
        {priceSuffix && <sub style={{ fontSize: "1rem", fontWeight: 500, color: MUTED }}>{priceSuffix}</sub>}
      </div>
      <p style={{ fontSize: ".9rem", color: MUTED, margin: ".6rem 0 1.4rem" }}>{description}</p>
      <ul style={{ listStyle: "none", padding: 0, marginBottom: "1.6rem" }}>
        {features.map((f) => (
          <li key={f} style={{ fontSize: ".875rem", padding: ".35rem 0", borderBottom: `1px solid ${BORDER}`, display: "flex", gap: ".5rem", color: INK }}>
            <span style={{ color: ACCENT, fontWeight: 700 }}>&#10003;</span>{f}
          </li>
        ))}
      </ul>
      <a href={ctaHref} target={ctaHref.startsWith("http") ? "_blank" : undefined} rel={ctaHref.startsWith("http") ? "noopener" : undefined} className={`landing-btn ${emphasized ? "landing-btn-primary" : "landing-btn-ghost"}`} style={{
        display: "block", textAlign: "center", padding: ".75rem 1rem", borderRadius: 7,
        fontSize: ".9rem", fontWeight: 700, textDecoration: "none",
      }}>
        {ctaLabel}
      </a>
    </div>
  );
}

export default function PricingZigzag({ headingColor = INK }: { headingColor?: string }) {
  return (
    <div>
      <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: ".6rem" }}>
        Pricing
      </div>
      <h2 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-.02em", marginBottom: "2.5rem", color: headingColor }}>
        Scale with confidence.
      </h2>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "1.6rem", alignItems: "stretch" }}>
        <Tier
          emphasized
          eyebrow="Pro"
          price="$19.99"
          priceSuffix="/mo"
          description="Managed cloud. Everything you need for a production AI team, without running your own infrastructure."
          features={["Up to 10 agents managed", "Hosted dashboard and real-time log", "Automated tribunal runs on schedule", "EU AI Act, ISO 42001, NIST AI RMF, and SOC 2 policy packs", "PDF + HTML evidence pack exports", "Custom policy rules", "Priority email support"]}
          ctaLabel="Get started free"
          ctaHref="/login"
        />
        <Tier
          eyebrow="Enterprise"
          price="Custom"
          description="For regulated industries, large deployments, on-prem needs."
          features={["Unlimited agents", "SSO / SAML integration", "On-premises deployment", "Custom policy packs and mapping"]}
          ctaLabel="Contact us"
          ctaHref="mailto:hello@teluvane.com"
        />
      </div>
    </div>
  );
}
