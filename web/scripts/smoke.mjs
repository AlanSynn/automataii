import { spawn } from "node:child_process";

const port = 5174;
const server = spawn("python3", ["-m", "http.server", String(port), "-d", "."], {
  cwd: new URL("..", import.meta.url),
  stdio: "ignore",
});

try {
  let lastError;
  for (let i = 0; i < 30; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/`);
      const html = await res.text();
      if (!res.ok) throw new Error(`index status ${res.status}`);
      if (!html.includes("MotionSmith Web")) throw new Error("index missing title");
      for (const asset of ["src/app.js", "src/automataii-core.js", "src/onnx-segmentation.js", "src/zip.js", "src/styles.css"]) {
        const assetRes = await fetch(`http://127.0.0.1:${port}/${asset}`);
        if (!assetRes.ok) throw new Error(`${asset} status ${assetRes.status}`);
      }
      console.log("smoke ok");
      process.exitCode = 0;
      break;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
  }
  if (process.exitCode !== 0) throw lastError || new Error("smoke failed");
} finally {
  server.kill();
}
