import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const roots = ["src", "scripts", "test"];
const files = roots.flatMap((root) => readdirSync(root).filter((file) => /\.(mjs|js)$/.test(file)).map((file) => join(root, file)));
let failed = false;
for (const file of files) {
  const result = spawnSync("node", ["--check", file], { stdio: "inherit" });
  if (result.status !== 0) failed = true;
}
if (failed) process.exit(1);
