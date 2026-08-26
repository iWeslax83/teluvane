// frontend/app/icon.tsx
import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#1a1714",
          borderRadius: 7,
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path
            d="M2 12 L4 12 L4.8 10.5 L5.6 12 L6.4 7 L7.2 15.5 L8 12 L9.5 12 L10.3 10.5 L11.1 12 L11.9 7 L12.7 15.5 L13.5 12 L15 12"
            stroke="#6f9db4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          />
          <path
            d="M15 12 L15.6 9 L16.2 12 L17 4 L17.8 18 L18.6 10 L19.2 13 L20 12 L21.5 12"
            stroke="#d4656d" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
