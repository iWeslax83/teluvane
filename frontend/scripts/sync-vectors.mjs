// Copies the Python-generated parity vectors into the frontend fixtures dir so
// the browser Merkle + chain verification libs are tested against the exact
// same cases as the Python implementation (Tasks 2 and 3).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");
const srcDir = join(repoRoot, "tests", "fixtures");
const destDir = join(here, "..", "lib", "__fixtures__");

mkdirSync(destDir, { recursive: true });

for (const name of ["merkle_vectors.json", "chain_vectors.json"]) {
  copyFileSync(join(srcDir, name), join(destDir, name));
  console.log(`synced ${name}`);
}
