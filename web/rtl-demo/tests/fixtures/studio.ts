import type { Page } from "@playwright/test";
export async function offline(page: Page) {
  await page.route("**/api/**", (r) => r.abort());
}
export async function fixtureChat(page: Page) {
  let bundle: any;
  const messages: any[] = [];
  let posts = 0;
  await page.route("**/api/**", async (r) => {
    const path = new URL(r.request().url()).pathname;
    if (path === "/api/cases/e203") {
      bundle = await (
        await page.request.get("/cases/e203/manifest.json")
      ).json();
      return r.fulfill({ json: bundle });
    }
    if (path === "/api/health")
      return r.fulfill({
        json: {
          capabilities: {
            chat: { available: true, missing: [] },
            verify: { available: false, missing: ["fixture"] },
          },
        },
      });
    if (path.endsWith("/events")) return r.abort();
    if (path.endsWith("/selection")) return r.fulfill({ json: {} });
    if (path.endsWith("/messages")) {
      posts++;
      const b = r.request().postDataJSON();
      messages.push({
        message_id: "test-" + posts,
        text: b.text,
        state: "answered",
        answer: "契约测试回复 " + posts,
        context_ref: b.context_ref,
        evidence_refs: [{ artifact_id: bundle.spec_artifact_id }],
      });
      return r.fulfill({ status: 202, json: messages.at(-1) });
    }
    if (path.startsWith("/api/sessions"))
      return r.fulfill({
        status: r.request().method() === "POST" ? 201 : 200,
        json: {
          session_id: "test-session",
          selection: { case_id: "e203", browsing_mode: "historical" },
          messages,
          operations: [],
        },
      });
    return r.abort();
  });
  return { messages, posts: () => posts };
}

export async function openChat(page: Page) {
  if (!(await page.locator(".chat-dialog").isVisible()))
    await page.getByRole("button", { name: "AI 对话", exact: true }).click();
}
