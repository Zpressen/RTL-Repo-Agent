import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { offline } from "../fixtures/studio";
test("downloads exact static single and comparison evidence offline", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  const b = await (await page.request.get("/cases/e203/manifest.json")).json();
  for (const compare of [false, true]) {
    if (compare)
      await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
    const next = page.waitForEvent("download");
    await page.getByRole("button", { name: "下载证据包", exact: true }).click();
    const d = await next;
    const p = await d.path();
    expect(p).toBeTruthy();
    const hash = createHash("sha256").update(readFileSync(p!)).digest("hex");
    const expected = compare
      ? b.evidence_packages.comparisons[0]
      : b.evidence_packages.single[b.comparison_pair.after_validation_id];
    expect(hash).toBe(expected.sha256);
  }
});
test("API fallback handles ZIP and errors without downloading error pages", async ({
  page,
}) => {
  const b = await (await page.request.get("/cases/e203/manifest.json")).json(),
    d = b.evidence_packages.single[b.comparison_pair.after_validation_id];
  const zip = await (await page.request.get(d.url)).body();
  delete b.evidence_packages;
  let bad = false;
  await page.route("**/cases/e203/manifest.json", (r) =>
    r.fulfill({ json: b }),
  );
  await page.route("**/api/**", (r) => {
    const p = new URL(r.request().url()).pathname;
    if (p.endsWith("/evidence.zip"))
      return bad
        ? r.fulfill({
            status: 409,
            json: { error: { message: "测试：材料绑定异常" } },
          })
        : r.fulfill({ contentType: "application/zip", body: zip });
    if (p === "/api/cases/e203") return r.fulfill({ json: b });
    if (p === "/api/health") return r.fulfill({ json: { capabilities: {} } });
    if (p.endsWith("/events")) return r.abort();
    if (p.endsWith("/selection")) return r.fulfill({ json: {} });
    if (p.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "download-fixture",
          selection: { case_id: "e203" },
          messages: [],
          operations: [],
        },
      });
    return r.abort();
  });
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  const next = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await next;
  bad = true;
  let count = 0;
  page.on("download", () => count++);
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await expect(page.locator("dialog[open]")).toContainText("材料绑定异常");
  expect(count).toBe(0);
});
