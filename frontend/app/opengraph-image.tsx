import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "80px 96px",
          background: "#f4efe6",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 40,
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 14,
              background: "#1a1714",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width="40" height="40" viewBox="92 92 216 216" fill="none">
          <rect x="96" y="102" width="208" height="52" fill="#f4efe6" />
          <path d="M96 178 H304 L200 300 Z M152 178 L200 234 L248 178 Z" fill="#f4efe6" fillRule="evenodd" />
          <circle cx="200" cy="204" r="13" fill="#6f9db4" />
        </svg>
          </div>
          <div style={{ fontSize: 40, fontWeight: 800, color: "#1a1714", letterSpacing: "-0.02em" }}>
            TELUVANE
          </div>
        </div>
        <div
          style={{
            fontSize: 52,
            fontWeight: 900,
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
            color: "#1a1714",
            maxWidth: 900,
            display: "flex",
            flexWrap: "wrap",
          }}
        >
          Prove what your <span style={{ color: "#2f5266" }}>AI agents</span> did.
        </div>
        <div
          style={{
            fontSize: 24,
            color: "#6b6458",
            marginTop: 24,
            maxWidth: 800,
          }}
        >
          Tamper-evident flight recorder and autonomous compliance tribunal for AI agents.
        </div>
      </div>
    ),
    { ...size }
  );
}
