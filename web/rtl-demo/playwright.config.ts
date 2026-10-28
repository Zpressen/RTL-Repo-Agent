import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
// Reuse optional local validation tools without installing browser assets into the app.
const cachedBrowser = fileURLToPath(
  new URL("../../.rtl-demo/browser-cache", import.meta.url),
);
const browserLibraries = fileURLToPath(
  new URL(
    "../../.rtl-demo/browser-deps/extracted/usr/lib/x86_64-linux-gnu",
    import.meta.url,
  ),
);
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && existsSync(cachedBrowser))
  process.env.PLAYWRIGHT_BROWSERS_PATH = cachedBrowser;
if (existsSync(browserLibraries))
  process.env.LD_LIBRARY_PATH = [browserLibraries, process.env.LD_LIBRARY_PATH]
    .filter(Boolean)
    .join(":");
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1366, height: 768 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
  },
  timeout: 30000,
});
