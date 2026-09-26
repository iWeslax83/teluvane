import { describe, it, expect } from "vitest";
import merkleVectors from "./__fixtures__/merkle_vectors.json";
import chainVectors from "./__fixtures__/chain_vectors.json";
import chainVectorsV2 from "./__fixtures__/chain_vectors_v2.json";
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

describe("chain verify parity for erasable (v2) events", () => {
  it("verifies a v2 chain, whose canonical strings carry a commitment instead of content", async () => {
    for (const e of chainVectorsV2.events) {
      expect(JSON.parse(e.canonical).v).toBe(2);
      expect(e.canonical).not.toContain("intent");
    }
    const res = await verifyChain(chainVectorsV2.events);
    expect(res.ok).toBe(true);
    expect(res.head).toBe(chainVectorsV2.events.at(-1)!.hash);
  });
  it("flags a v2 event whose commitment was swapped", async () => {
    const evts = chainVectorsV2.events.map((e: any) => ({ ...e }));
    evts[1] = { ...evts[1], canonical: evts[1].canonical.replace(/"payload_commitment": "[0-9a-f]{4}/, '"payload_commitment": "0000') };
    const res = await verifyChain(evts);
    expect(res.ok).toBe(false);
    expect(res.failAt).toBe(evts[1].seq);
  });
});
