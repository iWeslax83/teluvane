// frontend/app/blog/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import { blogPosts } from "@/lib/blogPosts";
import { BG, INK, ACCENT, MUTED, BORDER } from "@/lib/landingTheme";

export const metadata: Metadata = {
  title: "Blog: TELUVANE",
  description: "AI agent compliance, audit trails, and the frameworks that govern them, explained plainly.",
  alternates: { canonical: "/blog" },
};

export default function BlogIndex() {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: BG, color: INK, minHeight: "100dvh", lineHeight: 1.6 }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "4rem 1.5rem 6rem" }}>
        <Link href="/" style={{ color: ACCENT, fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>&larr; Back to homepage</Link>
        <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, margin: "1.6rem 0 .6rem" }}>
          Blog
        </div>
        <h1 style={{ fontSize: "clamp(2rem, 4.5vw, 2.6rem)", fontWeight: 900, letterSpacing: "-.03em", marginBottom: "2.5rem" }}>
          AI agent accountability, explained.
        </h1>

        <div>
          {blogPosts.map((post, i) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="landing-link"
              style={{
                display: "block",
                padding: "1.6rem 0",
                borderTop: i === 0 ? `1px solid ${BORDER}` : "none",
                borderBottom: `1px solid ${BORDER}`,
                textDecoration: "none",
                color: INK,
              }}
            >
              <div style={{ fontSize: ".8rem", color: MUTED, marginBottom: ".4rem" }}>{post.date}</div>
              <h2 style={{ fontSize: "1.3rem", fontWeight: 800, letterSpacing: "-.015em", marginBottom: ".4rem" }}>{post.title}</h2>
              <p style={{ fontSize: ".95rem", color: MUTED, maxWidth: 600 }}>{post.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
