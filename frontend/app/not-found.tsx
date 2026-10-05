// frontend/app/not-found.tsx
import type { Metadata } from "next";
import Link from "next/link";
import BrandMark from "@/components/BrandMark";

export const metadata: Metadata = { title: "Page not found: TELUVANE" };

export default function NotFound() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      style={{
        minHeight: "100dvh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 24,
        background: "#f4efe6",
        color: "#1a1714",
        textAlign: "center",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: "#1a1714",
          color: "#f4efe6",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <BrandMark size={28} dot="#6f9db4" />
      </div>
      <h1 style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-0.02em", margin: 0 }}>
        Page not found
      </h1>
      <p style={{ color: "#6b6458", maxWidth: 420, margin: 0 }}>
        The page you&apos;re looking for doesn&apos;t exist or has moved. Check the URL, or head back to
        the homepage.
      </p>
      <Link
        href="/"
        style={{
          marginTop: 8,
          display: "inline-flex",
          alignItems: "center",
          padding: ".75rem 1.6rem",
          borderRadius: 8,
          fontSize: ".95rem",
          fontWeight: 600,
          background: "#2f5266",
          color: "#fff",
          textDecoration: "none",
        }}
      >
        Back to homepage
      </Link>
    </main>
  );
}
