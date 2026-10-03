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
        <svg width="22" height="22" viewBox="92 92 216 216" fill="none">
          <rect x="96" y="102" width="208" height="52" fill="#f4efe6" />
          <path d="M96 178 H304 L200 300 Z M152 178 L200 234 L248 178 Z" fill="#f4efe6" fillRule="evenodd" />
          <circle cx="200" cy="204" r="13" fill="#6f9db4" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
