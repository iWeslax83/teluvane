import { describe, it, expect } from "vitest";
import merkleVectors from "./__fixtures__/merkle_vectors.json";
import chainVectors from "./__fixtures__/chain_vectors.json";
import { rootFromProof } from "./merkle";
import { verifyChain } from "./chainVerify";

describe("merkle parity with Python", () => {
  for (const [i, c] of merkleVectors.cases.entries()) {
    it(`case ${i} roots match`, async () => {
      for (let j = 0; j < c.leaves.length; j++) {
        const l = c.leaves[j];
        const r = await rootFromProof(l.org_id, l.session_id, l.chain_head, c.proofs[j]);
        expect(r).toBe(c.root);
      }
    });
  }
});

describe("chain verify parity with Python", () => {
  it("verifies the recorded chain", async () => {
    const res = await verifyChain(chainVectors.events);
    expect(res.ok).toBe(true);
    expect(res.head).toBe(chainVectors.events.at(-1)!.hash);
  });
  it("flags a tampered canonical string", async () => {
    const evts = chainVectors.events.map((e: any) => ({ ...e }));
    evts[0] = { ...evts[0], canonical: evts[0].canonical.replace(/}$/, " }") };
    const res = await verifyChain(evts);
    expect(res.ok).toBe(false);
    expect(res.failAt).toBe(evts[0].seq);
  });
});
