import { openChat } from "../fixtures/studio";
import { test, expect } from "@playwright/test";

test("deployed case navigation preserves an editable task conversation", async ({
  page,
}) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/?case=e203");
  await openChat(page);
  const composer = page.locator("textarea");
  await expect(composer).toBeEditable();
  await composer.fill("解释当前版本的验证依据");
  await expect(composer).toHaveValue("解释当前版本的验证依据");
  await page.reload();
  await openChat(page);
  await expect(composer).toBeEditable();
  await expect(composer).toHaveValue("解释当前版本的验证依据");
  for (const caseId of [
    "aes_cipher_system_hard",
    "aes_inv_cipher_top_system",
    "sdc_controller_system",
  ]) {
    await page.goto(`/?case=${caseId}`);
    await openChat(page);
    await expect(composer).toBeEditable();
    await expect(page.locator("body")).not.toContainText("undefined");
  }
});
