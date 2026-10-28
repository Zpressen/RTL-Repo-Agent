import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";

test("AES starts with its true initial report and discrete probes, then opens final real VCD", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_cipher_system_hard");
  await expect(page.locator(".result strong")).toHaveText("未通过");
  await expect(page.locator(".signal-mismatches")).toContainText(
    "text_out：287 次差异",
  );
  await expect(page.locator(".signal-mismatches")).toContainText(
    "done：12 次差异",
  );
  await expect(page.locator(".sample-metric")).toContainText("— / —");
  await expect(page.locator(".verification")).toContainText("完整VCD未留存");
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  await expect(page.locator(".probe-samples")).toContainText("离散采样");
  await expect(page.locator(".probe-table tbody tr")).toHaveCount(12);
  const first = await page.locator(".probe-table tbody tr").first().innerText();
  await page.getByRole("button", { name: "下一页", exact: true }).click();
  await expect(page.locator(".probe-table tbody tr").first()).not.toHaveText(
    first,
  );
  await page.getByRole("combobox", { name: "探针信号" }).selectOption("dcnt");
  await page
    .getByRole("button", { name: "查看差异附近探针 · 15 ps", exact: true })
    .click();
  await expect(page.getByRole("combobox", { name: "探针信号" })).toHaveValue(
    "text_out",
  );
  await page.locator('.timeline-step[data-step="complete"]').click();
  await expect(page.locator(".result strong")).toHaveText("通过");
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await expect(page.locator(".verification")).toContainText(
    "未发现另一次独立复验记录",
  );
  await expect(page.locator(".sidebar-metrics")).toContainText("8");
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
});

test("AES eight repairs link actual diffs, syntax rollback and regression to the correct baseline", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_cipher_system_hard");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(8);
  await page.locator('.trace-attempt[data-trial="3"]').click();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "3",
  );
  await expect(page.locator(".diff-source")).toContainText("@@ -");
  await expect(page.locator(".history-repair")).toContainText(
    "text_out：120 次差异",
  );
  await expect(page.locator(".history-repair")).not.toContainText(
    "null / null",
  );
  await expect(page.locator(".probe-samples")).toBeVisible();
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(page.locator(".signal-mismatches")).toContainText(
    "text_out：267 次差异",
  );
  await page.locator('.trace-attempt[data-trial="4"]').click();
  await expect(page.locator(".history-repair h2")).toContainText("已回退");
  await expect(page.locator(".history-repair")).toContainText("语法检查失败");
  await expect(page.locator(".probe-samples, .wave-canvas")).toHaveCount(0);
  await page
    .getByRole("button", { name: "查看语法工具日志 ↗", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toContainText(
    "Duplicate declaration",
  );
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.locator('.trace-attempt[data-trial="7"]').click();
  await expect(page.locator(".history-repair h2")).toContainText("已回退");
  await expect(
    page.locator(".history-repair .signal-mismatches"),
  ).toContainText("text_out：267 次差异");
  await page.locator('.trace-attempt[data-trial="8"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 6",
  );
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(page.locator(".signal-mismatches")).toContainText(
    "done：3 次差异",
  );
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await download;
  await page.reload();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "8",
  );
  await expect(page.locator(".baseline-binding")).toContainText("候选 6");
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(8);
});

test("AES small screen preserves clickable cards without nested side scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await offline(page);
  await page.goto("/?case=aes_cipher_system_hard&panel=repair");
  await page.locator('.trace-attempt[data-trial="8"]').click();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "8",
  );
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
