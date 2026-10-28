import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";
test("real replay pauses restarts and never executes", async ({ page }) => {
  await offline(page);
  await page.goto("/");
  await page.getByRole("button", { name: "从头回放", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "暂停回放", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator('.timeline-step[data-step="complete"]'),
  ).toContainText("尚未回放");
  await expect(
    page.locator('.timeline-step[data-step="complete"]'),
  ).not.toHaveAttribute("data-result", "pass");
  await page.getByRole("button", { name: "暂停回放", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "继续回放", exact: true }),
  ).toBeVisible();
  await page.locator(".timeline-step").nth(5).click();
  await expect(
    page.getByRole("tab", { name: "定位与修复", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("body")).toContainText("未单独记录");
});
