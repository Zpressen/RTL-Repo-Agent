import { test, expect } from "@playwright/test";
test("真实前后波形定位、缩放、游标与保持窗口", async ({ page }) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  await page.getByRole("tab", { name: "仿真与波形", exact: true }).click();
  await page
    .getByRole("button", { name: "修复前 · trial 5", exact: true })
    .click();
  await page.getByRole("button", { name: "定位差异" }).click();
  await expect(page.locator(".wave-controls")).toContainText("1045–1205 ps");
  await expect(page.locator(".cursor-caption")).toContainText("1125 ps");
  await page
    .getByRole("button", { name: "修复后 · 最终复验", exact: true })
    .click();
  await expect(page.locator(".wave-controls")).toContainText("1045–1205 ps");
  await expect(page.getByText("0 / 222", { exact: true })).toBeVisible();
  await expect(
    page.locator("svg text").filter({ hasText: "采样差异" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "+", exact: true }).click();
  await expect(page.locator(".wave-controls")).toContainText("1085–1165 ps");
  const chart = page.getByRole("img", { name: "真实 DUT 与参考设计仿真波形" });
  await chart.click({ position: { x: 500, y: 80 } });
  await expect(page.locator(".cursor-values")).toContainText(
    "wbck_o_wdat_dut:",
  );
  await page.screenshot({
    path: "test-results/rtl-studio-waveform.png",
    fullPage: true,
  });
});
