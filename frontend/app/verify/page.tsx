import type { Metadata } from "next";
import Link from "next/link";
import VerifyClient from "./VerifyClient";

export const metadata: Metadata = {
  title: "Verify a TELUVANE session on Avalanche",
  description:
    "Check that an AI agent session log has not changed since it was recorded. Runs in your browser, reads Avalanche Fuji directly, no account needed.",
};

export default function VerifyPage() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      style={{
        background: "#f4efe6",
        color: "#1a1714",
        fontFamily: "system-ui, -apple-system, sans-serif",
        minHeight: "100dvh",
      }}
    >
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "4rem 2rem 6rem", lineHeight: 1.55 }}>
        <Link
          href="/"
          style={{ color: "#2f5266", fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}
        >
          &larr; Back to homepage
        </Link>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, letterSpacing: "-.02em", margin: "1.5rem 0 .5rem" }}>
          Verify a session
        </h1>
        <p style={{ color: "#4a4540", lineHeight: 1.65, marginBottom: "1rem" }}>
          Confirm that a TELUVANE agent session log has not changed since it was recorded. Give it a
          session id that an organization has made public, or paste an evidence pack that was
          exported from TELUVANE.
        </p>
        <p style={{ color: "#4a4540", lineHeight: 1.65, marginBottom: 0 }}>
          The check recomputes the log&apos;s hash chain and Merkle root in your browser and reads the
          anchor record straight from Avalanche Fuji. TELUVANE never sees the request and cannot
          change the result.
        </p>
        <VerifyClient />
      </div>
    </main>
  );
}
