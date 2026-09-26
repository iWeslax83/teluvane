// Single source of truth for the landing page's demo session. demoSession.json holds the
// events, a chain of real SHA-256 hashes (built by scripts/build-demo-chain.mjs), and the
// finding the offline tribunal returns for this session (checked by tests/test_demo_session.py).
import raw from "./demoSession.json";
import type { ChainEvent } from "./chainVerify";

export interface DemoEventFields {
  kind: string;
  tool: string | null;
  intent: string;
  args: Record<string, unknown>;
  output: string;
  approvedBy: string | null;
  ts: string;
}

export interface DemoSession {
  orgId: string;
  sessionId: string;
  agentId: string;
  events: DemoEventFields[];
  tamper: { eventIndex: number; intent: string; args: Record<string, unknown> }[];
  chain: ChainEvent[];
}

export const DEMO = raw as unknown as DemoSession;

export function sortDeep(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === "object") {
    return Object.fromEntries(
      Object.keys(v as object).sort().map((k) => [k, sortDeep((v as Record<string, unknown>)[k])]),
    );
  }
  return v;
}

// Same fields and hashing as the server's event canonical form. Key order and whitespace
// are this demo's own; verifyChain takes the canonical string verbatim either way.
export function canonicalOf(prev: string, e: DemoEventFields): string {
  return JSON.stringify(
    sortDeep({
      prev,
      org_id: DEMO.orgId,
      agent_id: DEMO.agentId,
      session_id: DEMO.sessionId,
      kind: e.kind,
      intent: e.intent,
      tool: e.tool,
      args: e.args,
      output: e.output,
      approved_by: e.approvedBy,
      ts: e.ts,
    }),
  );
}

// The chain as an attacker edited it: one event's content changed, its stored hash left alone.
export function tamperedChain(index: number): ChainEvent[] {
  const edit = DEMO.tamper.find((t) => t.eventIndex === index);
  if (!edit) throw new Error(`no tamper variant for event ${index}`);
  return DEMO.chain.map((c, i) =>
    i === index
      ? { ...c, canonical: canonicalOf(c.prev_hash, { ...DEMO.events[i], intent: edit.intent, args: edit.args }) }
      : c,
  );
}

export function shortHash(h: string): string {
  return `${h.slice(0, 6)}...${h.slice(-4)}`;
}

export function describe(e: DemoEventFields): string {
  const to = typeof e.args.to === "string" ? ` to ${e.args.to}` : "";
  return `${e.tool ?? e.kind}${to}`;
}
