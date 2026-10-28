import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";

test("SDC starts at original per-output failure and opens independent final real wave", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=sdc_controller_system");
  await expect(page.locator(".result strong")).toHaveText("未通过");
  await expect(page.locator(".signal-mismatches")).toContainText(
    "wb_dat_o：23729 次差异",
  );
  await expect(page.locator(".signal-mismatches")).toContainText(
    "sd_dat_out_o：11750 次差异 · 首次 5 ps",
  );
  await expect(page.locator(".sample-metric")).toContainText("— / —");
  await expect(page.locator(".verification")).toContainText(
    "该版本VCD已被后续仿真覆盖",
  );
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  await expect(page.locator(".sidebar-metrics")).toContainText("17");
  await page.locator('.timeline-step[data-step="complete"]').click();
  await expect(page.locator(".result strong")).toHaveText("通过");
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await expect(page.locator(".verification")).toContainText(
    "各输出差异计数及首次时刻已与本版VCD",
  );
  await expect(page.locator(".verification")).toContainText("独立系统复验");
  await expect(
    page
      .locator(".wave-canvas svg text")
      .filter({ hasText: /^sd_cmd_oe_o_dut$/ }),
  ).toHaveCount(1);
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
});

test("SDC 17 candidates preserve rollback baselines and genuine before/after waveforms", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=sdc_controller_system");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(17);
  await page.locator('.trace-attempt[data-trial="1"]').click();
  await expect(page.locator(".history-repair h2")).toContainText("已回退");
  await expect(page.locator(".diff-source")).toContainText("@@ -");
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  await expect(page.locator(".signal-mismatches")).toContainText(
    "sd_cmd_oe_o：12074 次差异 · 首次 40 ps",
  );
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(page.locator(".wave-canvas")).toHaveCount(0);
  await expect(page.locator(".history-wave-comparison")).toContainText(
    "初始失败报告已保存",
  );
  await page.locator('.trace-attempt[data-trial="3"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：初始 RTL",
  );
  await page.locator('.trace-attempt[data-trial="8"]').click();
  await expect(page.locator(".history-repair h2")).toContainText("已回退");
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 7",
  );
  await page.locator('.trace-attempt[data-trial="17"]').click();
  await expect(page.locator(".baseline-binding")).toContainText(
    "修改基线：候选 16",
  );
  await expect(
    page.locator(".history-wave-comparison .result strong"),
  ).toHaveText("通过");
  await page
    .getByRole("combobox", { name: "变更文件" })
    .selectOption("sdc_serial_engine.v");
  await expect(page.locator(".diff-source")).toContainText("negedge");
  await page.getByRole("button", { name: "修改前波形", exact: true }).click();
  await expect(page.locator(".signal-mismatches")).toContainText(
    "sd_dat_out_o：998 次差异 · 首次 40 ps",
  );
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await download;
  await page.reload();
  await expect(page.locator(".history-repair")).toHaveAttribute(
    "data-trial",
    "17",
  );
  await expect(page.locator(".baseline-binding")).toContainText("候选 16");
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(17);
});

test("SDC compact layout shows the selected candidate without cross-case evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await offline(page);
  await page.goto("/?case=sdc_controller_system&panel=repair");
  await page.locator('.trace-attempt[data-trial="17"]').click();
  await expect(page.locator(".wave-canvas svg")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator("body")).not.toContainText("Booth");
});
