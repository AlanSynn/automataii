import { spawn, spawnSync } from "node:child_process";

const chrome = ["google-chrome", "chromium", "chromium-browser"].find((bin) => spawnSync("which", [bin], { stdio: "ignore" }).status === 0);
if (!chrome) throw new Error("No Chrome/Chromium binary available for browser smoke.");
const port = 5175;
const server = spawn("python3", ["-m", "http.server", String(port), "-d", "."], {
  cwd: new URL("..", import.meta.url),
  stdio: "ignore",
});
try {
  await new Promise((resolve) => setTimeout(resolve, 350));
  const run = spawnSync(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--virtual-time-budget=5000",
    "--dump-dom",
    `http://127.0.0.1:${port}/browser-smoke.html`,
  ], { encoding: "utf8" });
  if (run.status !== 0) throw new Error(run.stderr || run.stdout || "browser smoke failed");
  if (!run.stdout.includes("browser smoke ok")) throw new Error(run.stdout || "browser smoke did not finish");
  console.log("browser smoke ok");
} finally {
  server.kill();
}
