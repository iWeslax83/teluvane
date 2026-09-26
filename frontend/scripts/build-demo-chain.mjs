// Rebuilds the "chain" and "finding" blocks of lib/demoSession.json from its events, using
// the same canonical form as lib/demoSession.ts. Run after editing the demo events:
//   node scripts/build-demo-chain.mjs
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const path = join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "demoSession.json");
const d = JSON.parse(readFileSync(path, "utf8"));

const sortDeep = (v) =>
  Array.isArray(v)
    ? v.map(sortDeep)
    : v && typeof v === "object"
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortDeep(v[k])]))
      : v;

let prev = "GENESIS";
d.chain = d.events.map((e, i) => {
  const canonical = JSON.stringify(
    sortDeep({
      prev, org_id: d.orgId, agent_id: d.agentId, session_id: d.sessionId, kind: e.kind,
      intent: e.intent, tool: e.tool, args: e.args, output: e.output, approved_by: e.approvedBy, ts: e.ts,
    }),
  );
  const hash = createHash("sha256").update(canonical).digest("hex");
  const row = { seq: i + 1, prev_hash: prev, hash, canonical };
  prev = hash;
  return row;
});
writeFileSync(path, JSON.stringify(d, null, 2) + "\n");
console.log(`wrote ${d.chain.length} chained events to lib/demoSession.json`);
