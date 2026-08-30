// Browser port of the Python Merkle tree used for Avalanche session anchoring.
// Must stay byte-for-byte compatible with the Python implementation (Task 2);
// parity is enforced by lib/anchorVectors.test.ts against shared JSON vectors.

const enc = new TextEncoder();

export const LEAF_PREFIX = enc.encode("teluvane-anchor-leaf-v1:");
export const NODE_PREFIX = enc.encode("teluvane-anchor-node-v1:");

async function sha256(bytes: Uint8Array): Promise<Uint8Array> {
  const d = await globalThis.crypto.subtle.digest("SHA-256", bytes as BufferSource);
  return new Uint8Array(d);
}

function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

function fromHex(hex: string): Uint8Array {
  const h = hex.startsWith("0x") ? hex.slice(2) : hex;
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i * 2, 2), 16);
  return out;
}

function toHex(b: Uint8Array): string {
  return "0x" + Array.from(b).map((x) => x.toString(16).padStart(2, "0")).join("");
}

function cmp(a: Uint8Array, b: Uint8Array): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

export async function leafHash(
  orgId: string,
  sessionId: string,
  chainHeadHex: string,
): Promise<Uint8Array> {
  return sha256(
    concat(
      LEAF_PREFIX,
      enc.encode(orgId),
      enc.encode("|"),
      enc.encode(sessionId),
      enc.encode("|"),
      enc.encode(chainHeadHex),
    ),
  );
}

async function node(a: Uint8Array, b: Uint8Array): Promise<Uint8Array> {
  const [lo, ro] = cmp(a, b) <= 0 ? [a, b] : [b, a];
  return sha256(concat(NODE_PREFIX, lo, ro));
}

export async function rootFromProof(
  orgId: string,
  sessionId: string,
  chainHeadHex: string,
  proof: string[],
): Promise<string> {
  let acc = await leafHash(orgId, sessionId, chainHeadHex);
  for (const sib of proof) acc = await node(acc, fromHex(sib));
  return toHex(acc);
}
