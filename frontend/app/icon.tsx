// frontend/app/icon.tsx
import { ImageResponse } from "next/og";

export const size = { width: 48, height: 48 };
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
          borderRadius: 10,
        }}
      >
        <svg width="33" height="33" viewBox="92 92 216 216" fill="none">
          <rect x="96" y="102" width="208" height="52" fill="#f4efe6" />
          <path d="M96 178 H304 L200 300 Z M152 178 L200 234 L248 178 Z" fill="#f4efe6" fillRule="evenodd" />
          <circle cx="200" cy="204" r="13" fill="#6f9db4" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
