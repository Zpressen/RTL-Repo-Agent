import { test, expect } from "@playwright/test";
import { offline, openChat } from "../fixtures/studio";
for (const size of [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 390, height: 844 },
])
  test("reference layout " + size.width, async ({ page }) => {
    await page.setViewportSize(size);
    await offline(page);
    await page.goto("/?case=e203");
    await expect(page.getByRole("tab")).toHaveCount(5);
    await expect(page.locator(".timeline-step")).toHaveCount(8);
    await expect(page.locator(".chat-dialog")).not.toBeVisible();
    await openChat(page);
    await expect(page.locator("textarea")).toBeEditable();
    if (size.width > 1000)
      await expect(page.locator("textarea")).toBeInViewport();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page.locator(".primary-nav")).toHaveCount(0);
  });
