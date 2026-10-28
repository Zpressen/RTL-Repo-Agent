import { openChat } from "../fixtures/studio";
import { test, expect } from "@playwright/test";
// Contract-only model substitute. Never exported as investor evidence.
test("10轮对话、依据跳转、刷新恢复不重发", async ({ page }) => {
  let posts = 0;
  const messages: any[] = [];
  let bundle: any;
  await page.route("**/api/**", async (r) => {
    const path = new URL(r.request().url()).pathname;
    if (path === "/api/cases/e203") {
      const res = await r.fetch({
        url: "http://127.0.0.1:5173/cases/e203/manifest.json",
      });
      bundle = await res.json();
      return r.fulfill({ json: bundle });
    }
    if (path === "/api/health")
      return r.fulfill({
        json: {
          capabilities: {
            chat: { available: true, missing: [] },
            verify: { available: false, missing: ["test"] },
          },
        },
      });
    if (path.endsWith("/events")) return r.abort();
    if (path.endsWith("/messages")) {
      posts++;
      const body = r.request().postDataJSON();
      expect(body.context_ref).not.toHaveProperty("browsing_mode");
      messages.push({
        message_id: "m" + posts,
        text: body.text,
        context_ref: body.context_ref,
        state: "answered",
        answer: "契约测试回答 " + posts,
        evidence_refs: [{ artifact_id: bundle.spec_artifact_id }],
      });
      return r.fulfill({ status: 202, json: messages.at(-1) });
    }
    if (path.endsWith("/selection")) return r.fulfill({ json: {} });
    if (path.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "fixture-session",
          selection: {
            case_id: "e203",
            run_id: bundle.source_run_id,
            version_id: bundle.versions[1].version_id,
            validation_id: bundle.comparison_pair.after_validation_id,
            browsing_mode: "historical",
          },
          messages,
          operations: [],
        },
      });
    if (path.startsWith("/api/artifacts/")) {
      const id = path.split("/")[3];
      const res = await r.fetch({
        url: "http://127.0.0.1:5173" + bundle.content_urls[id],
      });
      return r.fulfill({ response: res });
    }
    return r.abort();
  });
  await page.goto("/");
  await openChat(page);
  for (let i = 1; i <= 10; i++) {
    await page
      .getByRole("textbox", { name: "与 RTL Agent 对话" })
      .fill("测试问题 " + i);
    await page.getByRole("button", { name: "发送 ↑", exact: true }).click();
    await expect(
      page.getByText("契约测试回答 " + i, { exact: true }),
    ).toBeVisible();
    if (i === 5)
      await page.getByRole("tab", { name: "RTL 代码", exact: true }).click();
  }
  await page.getByRole("button", { name: "查看依据 ↗" }).last().click();
  await expect(page.locator("dialog[open]")).toContainText("e203_exu_alu");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.reload();
  await openChat(page);
  await expect(
    page.getByText("契约测试回答 10", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("契约测试回答 10", { exact: true }),
  ).toBeInViewport({ ratio: 0.5 });
  expect(posts).toBe(10);
});
