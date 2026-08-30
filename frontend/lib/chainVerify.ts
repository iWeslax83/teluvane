// Browser port of the Python audit-log chain-digest verification (Task 3).
// Takes the server-supplied canonical string for each event verbatim (it does
// NOT re-serialize) and checks: sha256(canonical) === hash, and the parsed
// `prev` field links back to the previous event's hash, walking from "GENESIS".
// Parity is enforced by lib/anchorVectors.test.ts against shared JSON vectors.

const enc = new TextEncoder();

async function sha256Hex(s: string): Promise<string> {
  const d = await globalThis.crypto.subtle.digest("SHA-256", enc.encode(s) as BufferSource);
  return Array.from(new Uint8Array(d)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

export interface ChainEvent {
  seq: number;
  prev_hash: string;
  hash: string;
  canonical: string;
}

export async function verifyChain(
  events: ChainEvent[],
): Promise<{ ok: boolean; failAt?: number; head?: string }> {
  let prev = "GENESIS";
  for (const e of events) {
    if ((await sha256Hex(e.canonical)) !== e.hash) return { ok: false, failAt: e.seq };
    let parsedPrev: string;
    try {
      parsedPrev = JSON.parse(e.canonical).prev;
    } catch {
      return { ok: false, failAt: e.seq };
    }
    if (parsedPrev !== prev) return { ok: false, failAt: e.seq };
    prev = e.hash;
  }
  return { ok: true, head: events.length ? events[events.length - 1].hash : undefined };
}
