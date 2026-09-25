"use client";

import { useEffect, useState } from "react";
import { BG, SURFACE, BORDER, ACCENT, CRITICAL, INK, MUTED } from "@/lib/landingTheme";
import { landingMono } from "@/lib/landingFont";
import { verifyChain } from "@/lib/chainVerify";
import { DEMO, describe, shortHash, tamperedChain } from "@/lib/demoSession";

const MONO_STACK = landingMono.style.fontFamily;

type Result = { ok: boolean; failAt?: number };

export default function EvidenceLogCard({ size = "md" }: { size?: "md" | "lg" }) {
  const scale = size === "lg" ? 1.15 : 1;
  const [tampered, setTampered] = useState<number | null>(null);
  // The untouched chain verifies (tests/demoSession.test.ts proves it), so the first paint can
  // say INTACT without waiting for WebCrypto. Every click re-runs the real verifyChain.
  const [result, setResult] = useState<Result>({ ok: true });

  useEffect(() => {
    let cancelled = false;
    const chain = tampered === null ? DEMO.chain : tamperedChain(tampered);
    verifyChain(chain).then((r) => {
      if (!cancelled) setResult({ ok: r.ok, failAt: r.failAt });
    });
    return () => {
      cancelled = true;
    };
  }, [tampered]);

  const broken = !result.ok;
  const failIndex = (result.failAt ?? 0) - 1;

  function toggleTamper(i: number) {
    setTampered((prev) => (prev === i ? null : i));
  }

  return (
    <div style={{
      background: SURFACE,
      border: `1px solid ${BORDER}`,
      borderRadius: 10,
      overflow: "hidden",
      fontFamily: MONO_STACK,
      width: "100%",
      maxWidth: size === "lg" ? 480 : 420,
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: ".4rem",
        padding: `${0.6 * scale}rem ${0.9 * scale}rem`,
        borderBottom: `1px solid ${BORDER}`,
        background: BG,
      }}>
        <span style={{ fontSize: `${0.72 * scale}rem`, color: MUTED }}>{DEMO.sessionId}.chain</span>
      </div>
      <div style={{ padding: `${0.9 * scale}rem ${1.1 * scale}rem`, fontSize: `${0.8 * scale}rem`, lineHeight: 1.65, fontVariantNumeric: "tabular-nums" }}>
        {DEMO.events.map((e, i) => {
          const isTampered = tampered === i;
          const isBad = broken && i === failIndex;
          const isUntrusted = broken && i > failIndex;
          const shown = isTampered
            ? describe({ ...e, args: DEMO.tamper.find((t) => t.eventIndex === i)?.args ?? e.args })
            : describe(e);
          const last = i === DEMO.events.length - 1;
          return (
            <div key={i} style={{ marginBottom: last ? 0 : `${0.85 * scale}rem`, paddingBottom: last ? 0 : `${0.85 * scale}rem`, borderBottom: last ? "none" : `1px solid ${BORDER}` }}>
              <button
                type="button"
                className="evidence-row"
                onClick={() => toggleTamper(i)}
                aria-pressed={isTampered}
                aria-label={isTampered ? `Restore event #${i + 1}` : `Edit event #${i + 1} and verify the chain again`}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", padding: 0, margin: 0,
                  font: "inherit", color: "inherit",
                }}
              >
                <div style={{ color: MUTED, marginBottom: ".25rem" }}>event #{i + 1} &middot; {e.kind}</div>
                <div style={{ color: INK }}>
                  action: <span style={{ color: isTampered ? CRITICAL : ACCENT }}>{shown}</span>
                </div>
                <div style={{ color: INK }}>
                  hash:{" "}
                  <span style={{ color: isBad ? CRITICAL : MUTED, fontWeight: isBad ? 700 : 400 }}>
                    {isBad ? "MISMATCH" : isUntrusted ? "unverified" : shortHash(DEMO.chain[i].hash)}
                  </span>
                </div>
              </button>
              {last && (
                <div style={{ color: INK, marginTop: ".25rem" }}>
                  chain:{" "}
                  {broken ? (
                    <span style={{ color: CRITICAL, fontWeight: 700 }}>BROKEN at #{result.failAt}</span>
                  ) : (
                    <span style={{ color: ACCENT, fontWeight: 700 }}>INTACT</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: ".6rem",
        padding: `${0.55 * scale}rem ${1.1 * scale}rem`,
        borderTop: `1px solid ${BORDER}`,
        background: BG,
        fontSize: `${0.7 * scale}rem`,
        color: MUTED,
      }}>
        <span>Click an event to edit it. The same verifyChain code that /verify runs checks the chain in your browser.</span>
        {broken && (
          <button
            type="button"
            className="evidence-restore"
            onClick={() => setTampered(null)}
            style={{ background: "none", border: "none", color: ACCENT, font: "inherit", padding: 0, cursor: "pointer" }}
          >
            Restore
          </button>
        )}
      </div>
    </div>
  );
}
