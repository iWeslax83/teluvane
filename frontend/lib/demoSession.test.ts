import { describe, it, expect } from "vitest";
import { verifyChain } from "./chainVerify";
import { DEMO, canonicalOf, tamperedChain } from "./demoSession";

async function sha256Hex(s: string) {
  const d = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(s) as BufferSource);
  return Array.from(new Uint8Array(d)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

describe("demo session", () => {
  it("stored chain matches a fresh recomputation from the events", async () => {
    let prev = "GENESIS";
    for (const [i, e] of DEMO.events.entries()) {
      const canonical = canonicalOf(prev, e);
      expect(DEMO.chain[i].canonical).toBe(canonical);
      expect(DEMO.chain[i].hash).toBe(await sha256Hex(canonical));
      prev = DEMO.chain[i].hash;
    }
  });

  it("the untouched chain verifies", async () => {
    expect((await verifyChain(DEMO.chain)).ok).toBe(true);
  });

  it("editing any single event is caught at exactly that event", async () => {
    for (let i = 0; i < DEMO.events.length; i++) {
      const res = await verifyChain(tamperedChain(i));
      expect(res.ok).toBe(false);
      expect(res.failAt).toBe(i + 1);
    }
  });

  it("every tamper variant actually changes the event", () => {
    for (const t of DEMO.tamper) {
      const original = DEMO.chain[t.eventIndex].canonical;
      expect(tamperedChain(t.eventIndex)[t.eventIndex].canonical).not.toBe(original);
    }
  });
});
