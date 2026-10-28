import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";
test("legacy story URLs normalize and tab history survives", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_cipher_system_hard#/optimization");
  await expect(page).toHaveURL(/#\/workspace$/);
  await expect(page.locator(".case-select")).toHaveValue(
    "aes_cipher_system_hard",
  );
  await page.getByRole("tab", { name: "规格", exact: true }).click();
  await page.getByRole("tab", { name: "RTL 代码", exact: true }).click();
  await page.goBack();
  await expect(
    page.getByRole("tab", { name: "规格", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(
    page.getByRole("tab", { name: "规格", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.goto("/?case=e203&validation_id=missing#/workspace");
  await expect(page.locator(".context-error")).toContainText("不存在");
  await expect(page.locator(".result")).toHaveCount(0);
});
