"use client";
import Link from "next/link";
import { meetsWcagAA, contrastRatio } from "@/lib/contrast";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { sectionStyle, headingStyle, bodyStyle } from "@/lib/legalPageStyles";

const BG = "#f4efe6";
const TEXT = "#1a1714";
const MUTED = "#6b6458";
const ACCENT = "#2f5266";

const bgRatio = contrastRatio(BG, TEXT);
const accentRatio = contrastRatio(BG, ACCENT);

export default function AccessibilityClient() {
  const reducedMotion = useReducedMotion();

  return (
    <main id="main-content" tabIndex={-1} style={{ background: BG, color: TEXT, fontFamily: "system-ui, -apple-system, sans-serif", minHeight: "100dvh" }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "4rem 2rem 6rem" }}>
        <Link href="/" style={{ color: ACCENT, fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>&larr; Back to homepage</Link>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, letterSpacing: "-.02em", margin: "1.5rem 0 .5rem" }}>Accessibility</h1>
        <p style={{ color: MUTED, fontSize: ".9rem", marginBottom: "2.5rem" }}>
          Last updated 2026-08-22. How TELUVANE is built to work for keyboard users, screen reader users, and people who need reduced motion.
        </p>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Conformance statement</h2>
          <p style={bodyStyle}>
            TELUVANE targets WCAG 2.1 Level AA across the marketing site and the dashboard. We haven&apos;t had a third-party audit yet, so treat this as a good-faith statement of intent and current practice, not a certification. If you hit a barrier, tell us (see Contact below) and we&apos;ll fix it.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Keyboard navigation</h2>
          <p style={bodyStyle}>
            Every interactive element (links, buttons, form fields, the session table, the sidebar nav) is reachable and operable with Tab, Shift+Tab, and Enter/Space alone. Focus order follows visual order, and focus is never trapped except in modal dialogs, where Escape closes the dialog and returns focus to the element that opened it. Focus outlines are never removed with CSS.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Color contrast</h2>
          <p style={bodyStyle}>
            Body text and links on this page are checked against WCAG AA (4.5:1 for normal text, 3:1 for large text) using the same contrast utility (<code>lib/contrast.ts</code>) the app uses internally. Live result for the colors on this page:
          </p>
          <ul style={{ ...bodyStyle, paddingLeft: "1.2rem" }}>
            <li>
              Body text on background: {bgRatio.toFixed(2)}:1 &mdash;{" "}
              {meetsWcagAA(BG, TEXT) ? "passes AA" : "fails AA"}
            </li>
            <li>
              Accent links on background: {accentRatio.toFixed(2)}:1 &mdash;{" "}
              {meetsWcagAA(BG, ACCENT) ? "passes AA" : "fails AA"}
            </li>
          </ul>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Reduced motion</h2>
          <p style={bodyStyle}>
            Pages check the <code>prefers-reduced-motion</code> media query (via <code>lib/useReducedMotion.ts</code>) and skip decorative transitions and animations when it&apos;s set. Your browser is currently reporting:
          </p>
          <p style={{ ...bodyStyle, fontWeight: 600 }}>
            {reducedMotion ? "Reduced motion: on. Animations are disabled for you right now." : "Reduced motion: off. Your system isn't requesting reduced motion."}
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Screen readers</h2>
          <p style={bodyStyle}>
            Pages use semantic HTML (headings, lists, landmarks) instead of div soup, form fields have associated labels, and icon-only buttons carry an accessible name. We test regularly with VoiceOver on macOS.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Known gaps</h2>
          <p style={bodyStyle}>
            The insights charts don&apos;t yet have a text-table fallback for screen reader users. We&apos;re working on it.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Contact</h2>
          <p style={bodyStyle}>
            Found an accessibility barrier? Open an issue at{" "}
            <a href="https://github.com/iWeslax83/teluvane" target="_blank" rel="noopener" style={{ color: ACCENT }}>
              github.com/iWeslax83/teluvane
            </a>{" "}
            and we&apos;ll prioritize it.
          </p>
        </section>
      </div>
    </main>
  );
}
