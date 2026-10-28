import { openChat } from "../fixtures/studio";
import { test, expect } from "@playwright/test";

test("后台离线仍可输入，草稿在刷新和切换任务后保留", async ({ page }) => {
  await page.route("**/api/**", (r) => r.abort());
  await page.goto("/");
  await openChat(page);
  const input = page.getByRole("textbox", { name: "与 RTL Agent 对话" });
  await expect(input).toBeEditable();
  await input.fill("请解释这个模块的验证结果");
  await input.press("Enter");
  await expect(input).toHaveValue("请解释这个模块的验证结果");
  await expect(
    page.getByRole("button", { name: "发送 ↑", exact: true }),
  ).toBeDisabled();
  await page.reload();
  await openChat(page);
  await expect(input).toHaveValue("请解释这个模块的验证结果");
  await page
    .getByRole("combobox", { name: "演示任务" })
    .selectOption("aes_cipher_system_hard");
  await openChat(page);
  await expect(input).toHaveValue("");
  await input.fill("解释 AES 密钥扩展");
  await page.getByRole("combobox", { name: "演示任务" }).selectOption("e203");
  await openChat(page);
  await expect(input).toHaveValue("请解释这个模块的验证结果");
  await page.getByRole("button", { name: "重新连接", exact: true }).click();
  await expect(page.locator(".chat-error")).toContainText("草稿会保留");
  await expect(input).toBeEditable();
  await expect(input).toHaveValue("请解释这个模块的验证结果");
});

// Transport/model substitutes verify the composer only; no synthetic demo answers are shipped.
test("后台恢复后可手动重连发送，中文确认不误发，发送期间的新草稿保留", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const Native = window.EventSource;
    (window as any).__subscriptions = 0;
    window.EventSource = class extends Native {
      constructor(url: string | URL, options?: EventSourceInit) {
        super(url, options);
        (window as any).__subscriptions++;
      }
    };
  });
  const bundle = await (
    await page.request.get("/cases/e203/manifest.json")
  ).json();
  let online = false,
    posts = 0;
  const messages: any[] = [];
  let reply!: () => void;
  const responseReady = new Promise<void>((resolve) => {
    reply = resolve;
  });
  const session = () => ({
    session_id: "composer-session",
    selection: {
      case_id: "e203",
      run_id: bundle.source_run_id,
      version_id: bundle.versions.at(-1).version_id,
      validation_id: bundle.comparison_pair.after_validation_id,
      browsing_mode: "historical",
    },
    messages,
    operations: [],
  });
  await page.route("**/api/**", async (r) => {
    if (!online) return r.abort();
    const path = new URL(r.request().url()).pathname;
    if (path === "/api/health")
      return r.fulfill({
        json: {
          capabilities: {
            chat: { available: true, missing: [] },
            verify: { available: false, missing: [] },
          },
        },
      });
    if (path.endsWith("/events")) return r.abort();
    if (path.endsWith("/selection")) return r.fulfill({ json: {} });
    if (path.endsWith("/messages")) {
      posts++;
      const body = r.request().postDataJSON();
      await responseReady;
      messages.push({
        message_id: "m1",
        text: body.text,
        context_ref: body.context_ref,
        state: "answered",
        answer: "连接恢复后的契约测试回复",
        evidence_refs: [],
      });
      return r.fulfill({ status: 202, json: messages.at(-1) });
    }
    if (path.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: session(),
      });
    return r.abort();
  });
  await page.goto("/");
  await openChat(page);
  const input = page.getByRole("textbox", { name: "与 RTL Agent 对话" });
  await input.fill("解释当前验证结果");
  online = true;
  await page.getByRole("button", { name: "重新连接", exact: true }).click();
  const send = page.getByRole("button", { name: "发送 ↑", exact: true });
  await expect(send).toBeEnabled();
  await expect(input).toHaveValue("解释当前验证结果");
  await input.dispatchEvent("keydown", { key: "Enter", isComposing: true });
  await input.dispatchEvent("keydown", { key: "Enter", keyCode: 229 });
  expect(posts).toBe(0);
  await input.press("Enter");
  await expect.poll(() => posts).toBe(1);
  await input.fill("接下来解释写回数据");
  await page.getByRole("tab", { name: "规格", exact: true }).click();
  await page.getByRole("tab", { name: "架构", exact: true }).click();
  reply();
  await expect(
    page.getByText("连接恢复后的契约测试回复", { exact: true }),
  ).toBeVisible();
  await expect(input).toHaveValue("接下来解释写回数据");
  expect(messages[0].context_ref.view).toBe("workspace");
  expect(await page.evaluate(() => (window as any).__subscriptions)).toBe(1);
  await page.reload();
  await openChat(page);
  await expect(input).toHaveValue("接下来解释写回数据");
  expect(posts).toBe(1);
});
