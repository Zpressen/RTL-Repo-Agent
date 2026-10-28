import { test, expect } from "@playwright/test";
import { openChat } from "../fixtures/studio";

test("analysis shortcuts send with chat-only permissions and disabled execution shows a notice", async ({
  page,
}) => {
  const b = await (await page.request.get("/cases/e203/manifest.json")).json();
  const messages: any[] = [];
  let posts = 0,
    operations = 0;
  await page.route("**/api/**", (r) => {
    const p = new URL(r.request().url()).pathname;
    if (p === "/api/cases/e203") return r.fulfill({ json: b });
    if (p === "/api/health")
      return r.fulfill({
        json: {
          capabilities: {
            chat: { available: true },
            fix: { available: false },
            verify: { available: false },
          },
        },
      });
    if (p.endsWith("/events")) return r.abort();
    if (p.endsWith("/selection")) return r.fulfill({ json: {} });
    if (p.endsWith("/operations")) {
      operations++;
      return r.abort();
    }
    if (p.endsWith("/messages")) {
      posts++;
      const body = r.request().postDataJSON();
      const msg = {
        message_id: "analysis-" + posts,
        text: body.text,
        context_ref: body.context_ref,
        state: "answered",
        answer: "模型测试回复 " + posts,
        answer_source: "model",
      };
      messages.push(msg);
      return r.fulfill({ status: 202, json: msg });
    }
    if (p.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "analysis-session",
          selection: { case_id: "e203", browsing_mode: "historical" },
          messages,
          operations: [],
        },
      });
    return r.abort();
  });
  await page.goto("/");
  await openChat(page);
  await page.locator("textarea").fill("我的未发送草稿");
  for (const name of ["重新验证当前设计", "按预置规格生成并验证"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.locator(".chat-notice")).toContainText("暂不支持");
    await expect(page.locator("textarea")).toHaveValue("我的未发送草稿");
  }
  expect(posts).toBe(0);
  expect(operations).toBe(0);
  for (const [i, name] of [
    "这个设计如何拆分模块？",
    "解释当前验证结果",
    "分析失败原因与修复记录",
  ].entries()) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.locator(".agent-message").last()).toHaveText(
      "模型测试回复 " + (i + 1),
    );
  }
  expect(posts).toBe(3);
  expect(operations).toBe(0);
  await expect(page.locator(".messages")).toContainText("AI 模型回答");
});

test("a completed answer is recovered without SSE events or resending the question", async ({
  page,
}) => {
  const b = await (await page.request.get("/cases/e203/manifest.json")).json();
  let posts = 0,
    reads = 0,
    completed = false;
  const messages: any[] = [];
  await page.route("**/api/**", (r) => {
    const p = new URL(r.request().url()).pathname;
    if (p === "/api/cases/e203") return r.fulfill({ json: b });
    if (p === "/api/health")
      return r.fulfill({
        json: { capabilities: { chat: { available: true } } },
      });
    if (p.endsWith("/events")) return r.abort();
    if (p.endsWith("/selection")) return r.fulfill({ json: {} });
    if (p.endsWith("/messages")) {
      posts++;
      const body = r.request().postDataJSON();
      messages.push({
        message_id: "recover",
        text: body.text,
        context_ref: body.context_ref,
        state: "replying",
      });
      return r.fulfill({ status: 202, json: messages[0] });
    }
    if (p.startsWith("/api/sessions")) {
      reads++;
      const saved = messages.map((m) =>
        completed
          ? { ...m, state: "answered", answer: "没有 SSE 也恢复了最终回答" }
          : m,
      );
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "recover-session",
          selection: { case_id: "e203", browsing_mode: "historical" },
          messages: saved,
          operations: [],
        },
      });
    }
    return r.abort();
  });
  await page.goto("/");
  await openChat(page);
  await page.locator("textarea").fill("说明这里的握手逻辑");
  await page.getByRole("button", { name: "发送 ↑", exact: true }).click();
  await expect(page.locator(".agent-message")).toHaveText("Agent 正在分析…");
  await page.locator("textarea").fill("保留下一条草稿");
  completed = true;
  await expect(page.locator(".agent-message")).toHaveText(
    "没有 SSE 也恢复了最终回答",
    { timeout: 10000 },
  );
  expect(posts).toBe(1);
  expect(reads).toBeGreaterThan(2);
  await expect(page.locator("textarea")).toHaveValue("保留下一条草稿");
  await expect(
    page.getByRole("button", { name: "发送 ↑", exact: true }),
  ).toBeEnabled();
});
