import { test, expect } from "@playwright/test";
test("三个新增任务可切换并显示真实PASS报告和专属波形", async ({ page }) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  for (const [cid, signal, module] of [
    ["aes_cipher_system_hard", "text_out_dut", "aes_cipher_top"],
    ["aes_inv_cipher_top_system", "text_out_dut", "aes_inv_cipher_top"],
    ["sdc_controller_system", "wb_ack_o_dut", "sdc_controller"],
  ]) {
    await page.getByRole("combobox", { name: "演示任务" }).selectOption(cid);
    await expect(page).toHaveURL(new RegExp("case=" + cid));
    await page.getByRole("tab", { name: "RTL 代码", exact: true }).click();
    await expect(page.locator(".code-source")).toContainText(
      "module " + module,
    );
    await page.getByRole("tab", { name: "仿真与波形", exact: true }).click();
    await page.locator('.timeline-step[data-step="complete"]').click();
    await expect(page.locator(".result strong")).toHaveText("通过");
    await expect(
      page.getByText("报告未记录采样统计", { exact: true }),
    ).toBeVisible();
    await expect(page.locator(".wave-canvas svg")).toBeVisible();
    await expect(
      page
        .locator("svg text")
        .filter({ hasText: new RegExp("^" + signal + "$") }),
    ).toHaveCount(1);
    await page
      .getByRole("button", { name: "查看验证报告 ↗", exact: true })
      .click();
    await expect(page.locator("dialog[open]")).toContainText(
      "system_verify: PASS",
    );
    await page.getByRole("button", { name: "关闭", exact: true }).click();
  }
  await page.getByRole("textbox", { name: "跳转到时间刻度" }).fill("70000");
  await page.getByRole("button", { name: "跳转", exact: true }).click();
  await expect(page.locator(".wave-controls")).toContainText("69900–70100");
  await expect(page.locator(".cursor-caption")).toContainText("70000");
  await page.screenshot({
    path: "test-results/sdc-multi-case.png",
    fullPage: true,
  });
});
test("E203历史失败有明确解释并可返回最终通过", async ({ page }) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  await page.getByRole("tab", { name: "仿真与波形", exact: true }).click();
  await expect(page.getByText("0 / 222", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "修复前 · trial 5", exact: true })
    .click();
  await expect(page.locator(".history-explanation")).toContainText(
    "不是当前最终结果",
  );
  await page
    .getByRole("button", { name: "查看最终通过结果", exact: true })
    .click();
  await expect(page.getByText("0 / 222", { exact: true })).toBeVisible();
});
