import { describe, it, expect } from "vitest";
import { decideState, anchorRowKind, DOT, type DecideInput } from "./anchorState";

// A fully-agreeing input; each test overrides just what it needs.
const good: DecideInput = {
  anchored: true,
  root: "0xroot",
  proof: ["0xsib"],
  serverStatus: "verified",
  headStored: "h1",
  headMatches: true,
  chainOk: true,
  chainHead: "h1",
  localRoot: "0xroot",
  onchain: BigInt(1_700_000_000),
};

describe("decideState", () => {
  it("not-anchored when the session was never anchored", () => {
    expect(decideState({ ...good, anchored: false })).toEqual({ kind: "not-anchored" });
  });

  it("proof-missing when the anchor record has no root or no proof array", () => {
    expect(decideState({ ...good, root: null })).toEqual({ kind: "proof-missing" });
    expect(decideState({ ...good, proof: null })).toEqual({ kind: "proof-missing" });
  });

  it("rpc-unreachable when the on-chain read failed", () => {
    expect(decideState({ ...good, onchain: null })).toEqual({ kind: "rpc-unreachable" });
  });

  it("verified when local chain, local root and on-chain timestamp all agree", () => {
    expect(decideState(good)).toEqual({ kind: "verified" });
  });

  it("pending when not yet verified and the server still calls it pending", () => {
    expect(decideState({ ...good, onchain: BigInt(0), serverStatus: "pending" }))
      .toEqual({ kind: "pending" });
    expect(decideState({ ...good, onchain: BigInt(0), serverStatus: "submitted" }))
      .toEqual({ kind: "pending" });
  });

  it("mismatch when the root is not on Avalanche", () => {
    const s = decideState({ ...good, onchain: BigInt(0), serverStatus: "mismatch" });
    expect(s.kind).toBe("mismatch");
    if (s.kind === "mismatch") expect(s.why).toMatch(/not found on Avalanche/i);
  });

  it("mismatch when the locally recomputed hash does not match", () => {
    const s = decideState({ ...good, localRoot: "0xdifferent", serverStatus: "mismatch" });
    expect(s.kind).toBe("mismatch");
    if (s.kind === "mismatch") expect(s.why).toMatch(/does not match/i);
  });

  it("mismatch when the local chain head does not match the stored head", () => {
    expect(decideState({ ...good, chainHead: "other", serverStatus: "mismatch" }).kind)
      .toBe("mismatch");
  });
});

describe("DOT", () => {
  it("has a color for every state kind and no purple", () => {
    for (const k of ["not-anchored", "pending", "verified", "mismatch", "rpc-unreachable", "proof-missing"] as const) {
      expect(DOT[k]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});

describe("anchorRowKind", () => {
  it("maps the /sessions anchor field to a state kind", () => {
    expect(anchorRowKind("mined")).toBe("verified");
    expect(anchorRowKind("failed")).toBe("mismatch");
    expect(anchorRowKind("submitted")).toBe("pending");
    expect(anchorRowKind("pending")).toBe("pending");
    expect(anchorRowKind("none")).toBe("not-anchored");
    expect(anchorRowKind(undefined)).toBe("not-anchored");
  });
});
