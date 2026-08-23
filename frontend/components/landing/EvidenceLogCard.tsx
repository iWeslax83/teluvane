import { BG, SURFACE, BORDER, ACCENT, INK, MUTED } from "@/lib/landingTheme";

const MONO_STACK = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";

const events = [
  { id: "4469", type: "llm_call", action: "invoke_model", hash: "7a10e4...2f9c", prev: "e651ab...c003" },
  { id: "4470", type: "tool_call", action: "read_customer_record", hash: "3c02de...771a", prev: "7a10e4...2f9c" },
  { id: "4471", type: "tool_call", action: "send_email", hash: "9f2a1c...e08b", prev: "3c02de...771a" },
];

export default function EvidenceLogCard({ size = "md" }: { size?: "md" | "lg" }) {
  const scale = size === "lg" ? 1.15 : 1;
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
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${BORDER}` }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${BORDER}` }} />
        <span style={{ width: 7, height: 7, borderRadius: "50%", border: `1px solid ${BORDER}` }} />
        <span style={{ fontSize: `${0.72 * scale}rem`, color: MUTED, marginLeft: ".4rem" }}>agent_log.chain</span>
      </div>
      <div style={{ padding: `${0.9 * scale}rem ${1.1 * scale}rem`, fontSize: `${0.8 * scale}rem`, lineHeight: 1.65, fontVariantNumeric: "tabular-nums" }}>
        {events.map((e, i) => (
          <div key={e.id} style={{ marginBottom: i === events.length - 1 ? 0 : `${0.85 * scale}rem`, paddingBottom: i === events.length - 1 ? 0 : `${0.85 * scale}rem`, borderBottom: i === events.length - 1 ? "none" : `1px solid ${BORDER}` }}>
            <div style={{ color: MUTED, marginBottom: ".25rem" }}>event #{e.id} &middot; {e.type}</div>
            <div style={{ color: INK }}>
              action: <span style={{ color: ACCENT }}>{e.action}</span>
            </div>
            <div style={{ color: INK }}>
              hash: <span style={{ color: MUTED }}>{e.hash}</span>
            </div>
            {i === events.length - 1 && (
              <div style={{ color: INK, marginTop: ".25rem" }}>
                chain: <span style={{ color: ACCENT, fontWeight: 700 }}>INTACT</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
