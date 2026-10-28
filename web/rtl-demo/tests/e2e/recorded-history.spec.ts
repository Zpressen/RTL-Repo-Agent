import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";

test("one journey starts at the original failure and ends in the final pass", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203");
  await expect(page.locator(".sample-metric")).toContainText("222 / 222");
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await expect(
    page.locator(".wave-canvas svg text").filter({ hasText: /^采样差异/ }),
  ).toHaveCount(1);
  await expect(page.locator(".sidebar-metrics")).toContainText("39");
  await expect(
    page.getByRole("combobox", { name: "历史运行", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("第一轮");
  await expect(page.locator("body")).not.toContainText("第二轮");
  await page.locator('.timeline-step[data-step="complete"]').click();
  await expect(page.locator(".sample-metric")).toContainText("0 / 222");
  await page.getByRole("tab", { name: "仿真与波形", exact: true }).click();
  await expect(page.locator(".sample-metric")).toContainText("222 / 222");
});

test("39 cards show actual patches and waveforms using their accepted baselines", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(39);
  await page.locator('.trace-attempt[data-trial="4"]').click();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "4",
  );
  await expect(page.locator(".sample-metric")).toContainText("18 / 222");
  await expect(page.locator(".diff-source")).toContainText("@@ -");
  await page.locator('.trace-attempt[data-trial="1"]').click();
  await expect(page.locator(".history-repair")).toContainText("语法检查失败");
  await expect(page.locator(".history-repair .wave-canvas")).toHaveCount(0);
  await page.locator('.trace-attempt[data-trial="31"]').click();
  await expect(page.locator(".history-repair .wave-canvas")).toHaveCount(0);
  await page.locator('.trace-attempt[data-trial="39"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 35",
  );
  await expect(page.locator(".sample-metric")).toContainText("0 / 222");
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(page.locator(".sample-metric")).toContainText("1 / 222");
  await page.getByRole("button", { name: "本次候选波形", exact: true }).click();
  await expect(page.locator(".sample-metric")).toContainText("0 / 222");
  await page.reload();
  await expect(page.locator(".context-error")).not.toBeVisible();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "39",
  );
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 35",
  );
});

test("diagnosis switches the middle view and initial/candidate evidence downloads match selection", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203");
  const bundle = await (
    await page.request.get("/cases/e203/manifest.json")
  ).json();
  const initial = bundle.debug_history.runs[0].initial_validation_id;
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await download;
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(39);
  await page.locator('.trace-attempt[data-trial="4"]').click();
  await expect(page.locator(".history-diagnosis")).toContainText("未选中的 CSR");
  await expect(page.locator(".history-repair")).toHaveCount(0);
  await expect(page.locator(".history-diagnosis")).toHaveAttribute(
    "data-trial",
    "4",
  );
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
});
