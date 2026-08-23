import { BG, BORDER } from "@/lib/landingTheme";

export default function StickyMobileCta() {
  return (
    <div
      className="sticky-mobile-cta"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 40,
        background: BG,
        borderTop: `1px solid ${BORDER}`,
        padding: "0.75rem 1rem calc(0.75rem + env(safe-area-inset-bottom))",
        display: "none",
      }}
    >
      <a
        href="/login"
        className="landing-btn landing-btn-primary"
        style={{
          display: "block",
          textAlign: "center",
          width: "100%",
          padding: ".75rem 1rem",
          borderRadius: 8,
          fontSize: ".95rem",
          fontWeight: 700,
          textDecoration: "none",
        }}
      >
        Get started free
      </a>
      <style>{`
        @media (max-width: 767px) {
          .sticky-mobile-cta { display: block !important; }
        }
      `}</style>
    </div>
  );
}
