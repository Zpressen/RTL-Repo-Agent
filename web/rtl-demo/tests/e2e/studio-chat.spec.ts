import { openChat } from "../fixtures/studio";
import { test, expect } from "@playwright/test";
import { fixtureChat } from "../fixtures/studio";
test("three rounds retain sending panel and editable drafts", async ({
  page,
}) => {
  const f = await fixtureChat(page);
  await page.goto("/");
  await openChat(page);
  for (const [i, tab] of ["规格", "架构", "RTL 代码"].entries()) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.locator("textarea").fill("测试问题 " + i);
    await page.getByRole("button", { name: "发送 ↑", exact: true }).click();
    await expect(
      page.getByText("契约测试回复 " + (i + 1), { exact: true }),
    ).toBeVisible();
  }
  expect(f.messages.map((x) => x.context_ref.workspace_panel)).toEqual([
    "spec",
    "architecture",
    "code",
  ]);
  expect(f.posts()).toBe(3);
  await page.locator("textarea").fill("未发送草稿");
  await page.getByRole("tab", { name: "仿真与波形", exact: true }).click();
  await expect(page.locator("textarea")).toHaveValue("未发送草稿");
});
test("unfinished live run never borrows historical PASS or modules", async ({
  page,
}) => {
  const b = await (await page.request.get("/cases/e203/manifest.json")).json();
  await page.route("**/api/**", (r) => {
    const p = new URL(r.request().url()).pathname;
    if (p === "/api/cases/e203") return r.fulfill({ json: b });
    if (p === "/api/health")
      return r.fulfill({
        json: { capabilities: { chat: { available: false, missing: [] } } },
      });
    if (p === "/api/runs/private-live")
      return r.fulfill({
        json: {
          run_id: "private-live",
          case_id: "e203",
          origin: "live",
          versions: [],
          validations: [],
          modules: [],
        },
      });
    if (p.endsWith("/events")) return r.abort();
    if (p.endsWith("/selection")) return r.fulfill({ json: {} });
    if (p.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "live-fixture",
          selection: {
            case_id: "e203",
            run_id: "private-live",
            browsing_mode: "live",
            workspace_panel: "architecture",
          },
          messages: [],
          operations: [
            {
              operation_id: "op",
              run_id: "private-live",
              kind: "generate_and_verify",
              state: "running",
              stage: "architecture",
            },
          ],
        },
      });
    return r.abort();
  });
  await page.goto("/");
  await openChat(page);
  await expect(page.locator(".status-badge")).toContainText("实时执行中");
  await expect(page.locator(".sidebar-metrics")).not.toContainText("PASS");
  await expect(page.locator(".module-card")).toHaveCount(0);
  await expect(page.locator(".architecture")).toContainText("尚未产生模块规划");
  await expect(
    page.getByRole("button", { name: "下载证据包", exact: true }),
  ).toBeDisabled();
});
