"use client";

import { useState } from "react";
import { BG, SURFACE, BORDER, ACCENT, INK, MUTED } from "@/lib/landingTheme";

const MONO_STACK = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

const events = [
  { id: "4469", type: "llm_call", action: "invoke_model", hash: "7a10e4...2f9c" },
  { id: "4470", type: "tool_call", action: "read_customer_record", hash: "3c02de...771a" },
  { id: "4471", type: "tool_call", action: "send_email", hash: "9f2a1c...e08b" },
];

export default function EvidenceLogCard({ size = "md" }: { size?: "md" | "lg" }) {
  const scale = size === "lg" ? 1.15 : 1;
  const [tamperedId, setTamperedId] = useState<string | null>(null);
  const tamperedIndex = events.findIndex((e) => e.id === tamperedId);
  const chainBroken = tamperedIndex !== -1;

  function toggleTamper(id: string) {
    setTamperedId((prev) => (prev === id ? null : id));
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
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${chainBroken ? ACCENT : BORDER}` }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${chainBroken ? ACCENT : BORDER}` }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${chainBroken ? ACCENT : BORDER}` }} />
        <span style={{ fontSize: `${0.72 * scale}rem`, color: MUTED, marginLeft: ".4rem" }}>agent_log.chain</span>
      </div>
      <div style={{ padding: `${0.9 * scale}rem ${1.1 * scale}rem`, fontSize: `${0.8 * scale}rem`, lineHeight: 1.65, fontVariantNumeric: "tabular-nums" }}>
        {events.map((e, i) => {
          const isTampered = e.id === tamperedId;
          const broken = chainBroken && i >= tamperedIndex;
          return (
            <div key={e.id} style={{ marginBottom: i === events.length - 1 ? 0 : `${0.85 * scale}rem`, paddingBottom: i === events.length - 1 ? 0 : `${0.85 * scale}rem`, borderBottom: i === events.length - 1 ? "none" : `1px solid ${BORDER}` }}>
              <button
                type="button"
                className="evidence-row"
                onClick={() => toggleTamper(e.id)}
                aria-pressed={isTampered}
                aria-label={isTampered ? `Restore event #${e.id}` : `Simulate tampering with event #${e.id}`}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  background: "none", border: "none", padding: 0, margin: 0,
                  font: "inherit", color: "inherit",
                }}
              >
                <div style={{ color: MUTED, marginBottom: ".25rem" }}>event #{e.id} &middot; {e.type}</div>
                <div style={{ color: INK }}>
                  action: <span style={{ color: broken ? MUTED : ACCENT, textDecoration: isTampered ? "line-through" : undefined }}>{e.action}</span>
                </div>
                <div style={{ color: INK }}>
                  hash: <span style={{ color: broken ? ACCENT : MUTED, fontWeight: broken ? 700 : 400 }}>
                    {isTampered ? "MODIFIED" : broken ? "mismatch" : e.hash}
                  </span>
                </div>
              </button>
              {i === events.length - 1 && (
                <div style={{ color: INK, marginTop: ".25rem" }}>
                  chain:{" "}
                  {chainBroken ? (
                    <span style={{ color: ACCENT, fontWeight: 700 }}>BROKEN at #{tamperedId}</span>
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
        <span>Click an event to simulate tampering.</span>
        {chainBroken && (
          <button
            type="button"
            className="evidence-restore"
            onClick={() => setTamperedId(null)}
            style={{ background: "none", border: "none", color: ACCENT, font: "inherit", padding: 0, cursor: "pointer" }}
          >
            Restore
          </button>
        )}
      </div>
    </div>
  );
}
