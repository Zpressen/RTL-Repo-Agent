import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";
test("five views use real spec files and repair evidence", async ({ page }) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  await page.getByRole("tab", { name: "规格", exact: true }).click();
  await expect(page.locator(".spec-excerpt")).toContainText("Execution ALU");
  await page.getByRole("tab", { name: "架构", exact: true }).click();
  await expect(page.locator(".module-card")).toHaveCount(8);
  await page.getByRole("tab", { name: "RTL 代码", exact: true }).click();
  await expect(page.locator(".file-item")).toHaveCount(10);
  await page
    .getByRole("button", { name: "e203_defines.v", exact: true })
    .click();
  await expect(page.locator(".code-source")).toContainText("`define");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(page.locator(".repair-view")).toContainText("1 / 222");
  await expect(page.locator(".repair-view")).toContainText("未记录独立根因");
  await expect(page.getByRole("combobox", { name: "变更文件" })).toBeVisible();
  await page
    .getByRole("button", { name: "查看修复后 · 最终复验", exact: true })
    .click();
  await expect(page.locator(".sample-metric")).toContainText("0 / 222");
});
