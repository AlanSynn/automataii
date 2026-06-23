import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const out = "dist";
rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "src"), { recursive: true });
cpSync("index.html", join(out, "index.html"));
cpSync("src", join(out, "src"), { recursive: true });
const ortDist = join("node_modules", "onnxruntime-web", "dist");
const ortEntry = join(ortDist, "ort.all.min.mjs");
if (!existsSync(ortEntry)) {
  throw new Error("Missing ONNX Runtime Web assets. Run `npm --prefix web install` first.");
}
cpSync(ortDist, join(out, "vendor", "onnxruntime-web"), { recursive: true });
if (!existsSync(join(out, "vendor", "onnxruntime-web", "ort.all.min.mjs"))) {
  throw new Error("ONNX Runtime Web vendor copy failed.");
}
console.log(`Built static web app to ${out}/`);
