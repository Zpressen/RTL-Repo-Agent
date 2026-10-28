import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";

test("inverse AES opens true initial failure and final saved real wave", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_inv_cipher_top_system");
  await expect(page.locator(".result strong")).toHaveText("未通过");
  await expect(page.locator(".signal-mismatches")).toContainText(
    "text_out：37 次差异 · 首次 775 ps",
  );
  await expect(page.locator(".signal-mismatches")).toContainText(
    "done：1 次差异 · 首次 1015 ps",
  );
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  await expect(page.locator(".probe-samples")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "探针信号" })).toHaveValue(
    "done",
  );
  await expect(page.locator(".sidebar-metrics")).toContainText("代码修改");
  await expect(page.locator(".sidebar-metrics")).toContainText("4");
  await page.locator('.timeline-step[data-step="complete"]').click();
  await expect(page.locator(".result strong")).toHaveText("通过");
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await expect(page.locator(".verification")).toContainText(
    "未发现另一次独立复验记录",
  );
  await expect(page.locator(".sample-metric")).toContainText("— / —");
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
});

test("inverse AES keeps two unverified edits distinct from syntax failures and later simulation", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_inv_cipher_top_system");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(4);
  for (const n of [1, 2]) {
    await page.locator(`.trace-attempt[data-trial="${n}"]`).click();
    await expect(page.locator(".history-repair h2")).toContainText(
      "已保留 · 未单独验证",
    );
    await expect(page.locator(".diff-source")).toContainText("@@ -");
    await expect(page.locator(".history-repair")).not.toContainText(
      "语法检查失败",
    );
    await expect(
      page.locator(
        ".history-repair .probe-samples, .history-repair .wave-canvas",
      ),
    ).toHaveCount(0);
    await expect(page.locator(".repair-cards .card").nth(1)).not.toContainText(
      "37 次差异",
    );
  }
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 1",
  );
  await page
    .getByRole("button", { name: "查看修改状态 ↗", exact: true })
    .click();
  await expect(page.locator("dialog[open]")).toContainText(
    "未单独执行语法或仿真检查",
  );
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.locator('.trace-attempt[data-trial="3"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 2",
  );
  await expect(page.locator(".signal-mismatches")).toContainText(
    "text_out：34 次差异 · 首次 805 ps",
  );
  await expect(page.locator(".signal-mismatches")).toContainText(
    "done：9 次差异",
  );
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  await expect(page.locator(".probe-samples")).toBeVisible();
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(
    page.locator(".history-wave-comparison .result strong"),
  ).toHaveText("未验证");
  await expect(
    page.locator(".history-wave-comparison .probe-samples"),
  ).toHaveCount(0);
  await page.locator('.trace-attempt[data-trial="4"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 3",
  );
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await download;
  await page.reload();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "4",
  );
  await expect(page.locator(".baseline-binding")).toContainText("候选 3");
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(4);
  await page.locator('.timeline-step[data-step="syntax"]').click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(0);
});

test("inverse AES compact view keeps evidence and task identity", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await offline(page);
  await page.goto("/?case=aes_inv_cipher_top_system&panel=repair");
  await page.locator('.trace-attempt[data-trial="4"]').click();
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator("body")).not.toContainText("Booth");
});
