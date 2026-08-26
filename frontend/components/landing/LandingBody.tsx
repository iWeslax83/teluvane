// frontend/components/landing/LandingBody.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import EvidenceLogCard from "./EvidenceLogCard";
import PricingZigzag from "./PricingZigzag";
import Cta from "./Cta";
import Footer from "./Footer";
import StickyMobileCta from "./StickyMobileCta";
import LandingInteractionStyles from "./LandingInteractionStyles";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { BG, INK, ACCENT, MUTED, BORDER } from "@/lib/landingTheme";
import { landingMono } from "@/lib/landingFont";

const MONO_STACK = landingMono.style.fontFamily;

function FadeInSection({ children, style, id, eager }: { children: React.ReactNode; style?: React.CSSProperties; id?: string; eager?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(!!eager);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (eager) return;
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { threshold: 0.2 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [eager]);

  return (
    <div
      ref={ref}
      id={id}
      className="fade-section"
      style={{
        opacity: reducedMotion || visible ? 1 : 0,
        transition: reducedMotion ? "none" : "opacity 250ms ease-out",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

const stats = [
  { num: "€35M", text: "Maximum fine for non-compliance with EU AI Act obligations, or 7% of global revenue." },
  { num: "2026", text: "Article 50 transparency obligations (chatbot and synthetic-media disclosure) take effect. Full high-risk obligations are delayed to December 2027 under the Digital Omnibus." },
  { num: "Art.15", text: "Robustness and cybersecurity requirements your agent logs must now demonstrate." },
];

const trustPoints = [
  {
    title: "Org isolation is enforced in code, not just convention.",
    desc: "Every database query is scoped to an organization at the data-access layer. A query missing that scope throws before it runs, rather than depending on every developer remembering to filter correctly.",
    code: "query.where(org_id=current_org.id)  # required, or the query throws",
  },
  {
    title: "Two separate credential paths.",
    desc: "Dashboard logins (Supabase, JWT verified against Supabase's published keys) and agent event ingestion (per-org API keys) never share credentials. A leaked dashboard session can't be used to forge log entries, and vice versa.",
    code: "verify_jwt(session) != verify_api_key(org_key)  # disjoint paths",
  },
  {
    title: "The hash chain detects tampering, it doesn't prevent it.",
    desc: "A privileged database user can still edit a stored row. What the chain guarantees is that the edit becomes visible the next time anyone verifies the log, instead of staying silent.",
    code: "sha256(event[i-1].hash + event[i].payload) == event[i].hash",
  },
];

const steps = [
  {
    title: "Connect",
    desc: "Point Claude Desktop or Claude Code at the TELUVANE MCP server with one config file, no code in the agent. Any other agent can POST to /events with an API key.",
    artifact: '{\n  "mcpServers": {\n    "teluvane": {\n      "url": "https://api.teluvane.com/mcp"\n    }\n  }\n}',
  },
  {
    title: "Recorder",
    desc: "Every agent action, LLM call, tool invocation, and result is appended to a SHA-256 hash-chained log. Any silent edit breaks the chain immediately.",
    artifact: "event #4471 · tool_call\naction: send_email\nhash: 9f2a1c...e08b\nappended, chain: INTACT",
  },
  {
    title: "Tribunal",
    desc: "An autonomous multi-agent panel audits the full log against a structured policy pack, EU AI Act, ISO 42001, NIST AI RMF, or SOC 2, citing evidence, article references, and a confidence score for each finding.",
    artifact: 'finding: EU AI Act Art.15\nconfidence: 0.94\n"Model card missing robustness\ntest results for event #4210"',
  },
  {
    title: "Evidence Pack",
    desc: "One click exports an auditor-ready report: incident summary, violation table, full action log, and chain-integrity status, formatted for regulators.",
    artifact: "evidence_pack_2026-08-26.pdf\n42 events · 1 finding\nchain: INTACT · exported",
  },
];

export default function LandingBody() {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: BG, color: INK, lineHeight: 1.6 }}>
      <LandingInteractionStyles />
      <noscript>
        <style>{".fade-section{opacity:1 !important;}"}</style>
      </noscript>

      <FadeInSection id="opening" eager style={{ padding: "4.5rem 1.5rem 5rem" }}>
        <div style={{
          maxWidth: 1080, margin: "0 auto",
          display: "flex", flexWrap: "wrap-reverse", gap: "3rem", alignItems: "center",
        }}>
          <div style={{ flex: "1 1 420px", minWidth: 0 }}>
            <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: "1rem" }}>
              AI agent accountability
            </div>
            <h1 style={{ fontSize: "clamp(2.3rem, 5.2vw, 3.4rem)", fontWeight: 900, letterSpacing: "-.045em", lineHeight: 1.06, marginBottom: "1.2rem" }}>
              Every AI agent action, <span style={{ color: ACCENT }}>logged and hash-chained</span>.
            </h1>
            <p style={{ fontSize: "1.1rem", color: MUTED, lineHeight: 1.55, marginBottom: "2rem", maxWidth: 520 }}>
              Tamper one row and the chain breaks visibly. An autonomous tribunal audits the log and exports a regulator-ready evidence pack.
            </p>
            <div style={{ display: "flex", gap: ".75rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
              <a href="/login" className="landing-btn landing-btn-primary" style={{
                display: "inline-flex", alignItems: "center", padding: ".75rem 1.6rem",
                borderRadius: 8, fontSize: ".95rem", fontWeight: 700, textDecoration: "none",
              }}>
                Get started free
              </a>
              <a href="https://github.com/iWeslax83/teluvane" target="_blank" rel="noopener" className="landing-btn landing-btn-ghost landing-link" style={{
                display: "inline-flex", alignItems: "center", padding: ".75rem 1.6rem",
                borderRadius: 8, fontSize: ".95rem", fontWeight: 600, textDecoration: "none",
              }}>
                View on GitHub
              </a>
            </div>
            <div style={{ fontSize: ".82rem", color: MUTED, display: "flex", alignItems: "center", gap: ".5rem" }}>
              <span>Built with</span>
              <span>LangGraph</span>
              <span style={{ width: 3, height: 3, borderRadius: "50%", background: BORDER, display: "inline-block" }}></span>
              <span>Claude</span>
              <span style={{ width: 3, height: 3, borderRadius: "50%", background: BORDER, display: "inline-block" }}></span>
              <span>FastAPI</span>
            </div>
          </div>
          <div style={{ flex: "1 1 380px", minWidth: 0, display: "flex", justifyContent: "center" }}>
            <EvidenceLogCard size="lg" />
          </div>
        </div>
      </FadeInSection>

      <FadeInSection id="problem" style={{ padding: "4.5rem 1.5rem", borderTop: `1px solid ${BORDER}` }}>
        <div style={{ maxWidth: 1080, margin: "0 auto" }}>
          <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: ".6rem" }}>The problem</div>
          <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.4rem)", fontWeight: 800, letterSpacing: "-.025em", lineHeight: 1.15, marginBottom: "2.5rem", maxWidth: 640 }}>
            The EU AI Act asks for proof, not just logs.
          </h2>
          <div style={{ display: "flex", flexWrap: "wrap" }}>
            {stats.map(({ num, text }, i) => (
              <div key={num} style={{
                flex: "1 1 220px",
                padding: "0 1.6rem",
                borderLeft: i === 0 ? "none" : `1px solid ${BORDER}`,
                marginBottom: "1.5rem",
              }}>
                <div style={{ fontSize: "2.1rem", fontWeight: 900, letterSpacing: "-.02em", color: ACCENT, fontFamily: MONO_STACK, fontVariantNumeric: "tabular-nums" }}>{num}</div>
                <p style={{ fontSize: ".85rem", color: MUTED, marginTop: ".4rem" }}>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </FadeInSection>

      <FadeInSection id="how" style={{ padding: "4.5rem 1.5rem", borderTop: `1px solid ${BORDER}` }}>
        <div style={{ maxWidth: 1080, margin: "0 auto" }}>
          <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: ".6rem" }}>How it works</div>
          <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 2.4rem)", fontWeight: 800, letterSpacing: "-.025em", marginBottom: "2.8rem", maxWidth: 640 }}>
            Four steps from first action to court-ready evidence.
          </h2>
          <div>
            {steps.map(({ title, desc, artifact }, i) => (
              <div key={title} style={{ display: "flex", gap: "1.4rem" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                  <div style={{
                    width: 34, height: 34, borderRadius: "50%",
                    border: `1.5px solid ${ACCENT}`, color: ACCENT,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontFamily: MONO_STACK, fontSize: ".8rem", fontWeight: 700,
                  }}>
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  {i !== steps.length - 1 && (
                    <div style={{ width: 1, flex: 1, background: BORDER, margin: ".4rem 0" }} />
                  )}
                </div>
                <div style={{
                  paddingBottom: i === steps.length - 1 ? 0 : "2.2rem",
                  display: "flex", flexWrap: "wrap", gap: "1.6rem", width: "100%",
                }}>
                  <div style={{ flex: "1 1 260px" }}>
                    <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: ".4rem" }}>{title}</h3>
                    <p style={{ fontSize: ".9rem", color: MUTED, maxWidth: 480 }}>{desc}</p>
                  </div>
                  <div style={{
                    flex: "1 1 260px", maxWidth: 340,
                    fontFamily: MONO_STACK, fontSize: ".76rem", lineHeight: 1.6,
                    color: INK, whiteSpace: "pre-wrap",
                    border: `1px solid ${BORDER}`, borderLeft: `3px solid ${ACCENT}`,
                    borderRadius: 4, padding: ".7rem .9rem", alignSelf: "flex-start",
                  }}>
                    {artifact}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </FadeInSection>

      <FadeInSection id="proof" style={{ padding: "4.5rem 1.5rem", background: INK }}>
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: "#6f9db4", marginBottom: ".6rem" }}>Proof</div>
          <h2 style={{ fontSize: "clamp(1.7rem, 3.8vw, 2.3rem)", fontWeight: 800, letterSpacing: "-.02em", marginBottom: "1.2rem", maxWidth: 620, color: BG }}>
            Every read re-verifies the whole chain, not just the last row.
          </h2>
          <p style={{ fontSize: ".98rem", color: "#a8a199", maxWidth: 620, marginBottom: "1.6rem" }}>
            Each event stores the hash of the one before it. Change a single byte in event #14 and every event after it, up to #4471, fails verification the next time anyone opens the log.
          </p>
          <div style={{ fontFamily: MONO_STACK, fontSize: ".9rem", color: BG, border: "1px solid #33302b", borderLeft: "3px solid #6f9db4", padding: "1rem 1.2rem", background: "#22201d", fontVariantNumeric: "tabular-nums" }}>
            verify(chain) &rarr; 4471/4471 events valid &middot; <span style={{ color: "#6f9db4", fontWeight: 700 }}>INTACT</span>
          </div>
        </div>
      </FadeInSection>

      <FadeInSection id="trust" style={{ padding: "4.5rem 1.5rem", borderTop: `1px solid ${BORDER}` }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div style={{ fontSize: ".78rem", fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: ACCENT, marginBottom: ".6rem" }}>Security</div>
          <h2 style={{ fontSize: "clamp(1.6rem, 3.6vw, 2.1rem)", fontWeight: 800, letterSpacing: "-.02em", marginBottom: "1rem", maxWidth: 560 }}>
            We&apos;re early-stage. Here&apos;s what&apos;s already true.
          </h2>
          <p style={{ fontSize: ".95rem", color: MUTED, maxWidth: 560, marginBottom: "2rem" }}>
            No SOC 2 report yet, no formal certification. Rather than a badge we haven&apos;t earned, here&apos;s how the system is actually built.
          </p>
          <div>
            {trustPoints.map(({ title, desc, code }, i) => (
              <div key={title} style={{ padding: "1.1rem 0", borderTop: i === 0 ? "none" : `1px solid ${BORDER}` }}>
                <h3 style={{ fontSize: ".98rem", fontWeight: 700, marginBottom: ".35rem" }}>{title}</h3>
                <p style={{ fontSize: ".88rem", color: MUTED, maxWidth: 560, marginBottom: ".6rem" }}>{desc}</p>
                <div style={{
                  fontFamily: MONO_STACK, fontSize: ".76rem", color: INK,
                  background: "#efe9dd", borderRadius: 4, padding: ".45rem .7rem",
                  maxWidth: 560, overflowX: "auto",
                }}>
                  {code}
                </div>
              </div>
            ))}
          </div>
        </div>
      </FadeInSection>

      <FadeInSection id="pricing" style={{ padding: "4.5rem 1.5rem", borderTop: `1px solid ${BORDER}` }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          <PricingZigzag />
        </div>
      </FadeInSection>

      <div id="cta-footer">
        <Cta />
        <Footer />
      </div>
      <StickyMobileCta />
    </main>
  );
}
