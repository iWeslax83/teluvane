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
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
              <path
                d="M2 12 L4 12 L4.8 10.5 L5.6 12 L6.4 7 L7.2 15.5 L8 12 L9.5 12 L10.3 10.5 L11.1 12 L11.9 7 L12.7 15.5 L13.5 12 L15 12"
                stroke="#6f9db4" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
              />
              <path
                d="M15 12 L15.6 9 L16.2 12 L17 4 L17.8 18 L18.6 10 L19.2 13 L20 12 L21.5 12"
                stroke="#d4656d" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
              />
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
            color: "#8a8275",
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
