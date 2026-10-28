import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";
for (const cid of [
  "e203",
  "aes_cipher_system_hard",
  "aes_inv_cipher_top_system",
  "sdc_controller_system",
])
  test("removed RI route " + cid, async ({ page }) => {
    await offline(page);
    await page.goto("/?case=" + cid + "#/optimization");
    await expect(page).toHaveURL(/#\/workspace$/);
    await expect(page.getByRole("tab")).toHaveCount(5);
    await expect(page.locator(".primary-nav")).toHaveCount(0);
  });
