import { test, expect } from "@playwright/test";
import { offline, openChat } from "../fixtures/studio";

test("repair sidebar exposes the complete recorded debug loop and linked evidence", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  const trace = page.getByRole("region", { name: "Agent Trace 调试流程" });
  await expect(trace.locator(".trace-card")).toHaveCount(1);
  await expect(trace.locator(".trace-attempt")).toHaveCount(7);
  const repair = trace.locator('.trace-card[data-step="repair"]');
  await expect(repair.locator(".trace-summary")).toBeVisible();
  await expect(repair.locator(".trace-step-body")).toHaveCount(0);
  await trace.locator('.trace-attempt[data-trial="5"]').click();
  const trial = page.locator(".trace-dialog");
  await expect(trial).toContainText("Booth low-part alignment");
  await expect(trial).toContainText("e203_exu_muldiv.v");
  await expect(trial).toContainText("wbck_o_wdat");
  await expect(trial).toContainText("接受此候选");
  await trial
    .getByRole("button", { name: "查看候选 5 报告与波形 ↗", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "仿真与波形", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".selection-info")).toContainText("before");
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
  await openChat(page);
  await expect(page.locator("textarea")).toBeEditable();
  await expect(page.locator("textarea")).toBeInViewport();
});

test("trace replay never shows future fixes and SDC uses its own debug", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  await page.getByRole("button", { name: "从头回放", exact: true }).click();
  await page.getByRole("button", { name: "暂停回放", exact: true }).click();
  const trace = page.locator(".agent-trace");
  await expect(trace.locator(".trace-attempt")).toHaveCount(0);
  await expect(trace).not.toContainText("Separate initial overlap calculation");
  await page.goto("/?case=sdc_controller_system");
  await page.getByRole("tab", { name: "定位与修复", exact: true }).click();
  await expect(trace.locator(".trace-card")).toHaveCount(1);
  await expect(trace).not.toContainText("Booth");
  await expect(trace.locator('.trace-attempt')).toHaveCount(17);
});

test("each left phase shows only its own trace and tabs keep the phase aligned", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history");
  const trace = page.locator(".agent-trace");
  await openChat(page);
  await page.locator("textarea").fill("保留的草稿");
  await page.getByRole("button", { name: "收起对话", exact: true }).click();
  for (const id of [
    "spec",
    "architecture",
    "rtl",
    "syntax",
    "verify",
    "diagnose",
    "repair",
    "complete",
  ]) {
    await page.locator('.timeline-step[data-step="' + id + '"]').click();
    await expect(trace.locator(".trace-card")).toHaveCount(1);
    await expect(trace.locator(".trace-card")).toHaveAttribute("data-step", id);
    await expect(page.locator(".timeline-step.active")).toHaveAttribute(
      "data-step",
      id,
    );
    if (id === "complete") {
      await expect(trace).toContainText("独立系统复验通过");
      await expect(trace).not.toContainText("尚未到达");
    }
  }
  for (const [tab, id] of [
    ["规格", "spec"],
    ["架构", "architecture"],
    ["RTL 代码", "rtl"],
    ["定位与修复", "repair"],
  ]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await expect(trace.locator(".trace-card")).toHaveAttribute("data-step", id);
    await expect(page.locator(".timeline-step.active")).toHaveAttribute(
      "data-step",
      id,
    );
  }
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
  await openChat(page);
  await expect(page.locator("textarea")).toHaveValue("保留的草稿");
  await expect(page.locator("textarea")).toBeInViewport();
});

test("compact cards open details without nested trace scrollbars and chat is opt-in", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203&run_id=e203-demo-v1-history&panel=repair#/workspace");
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
  expect(
    await page
      .locator(".agent-trace")
      .evaluate(
        (root) =>
          [...root.querySelectorAll("*")].filter(
            (e) =>
              e.scrollHeight > e.clientHeight + 1 &&
              ["auto", "scroll"].includes(getComputedStyle(e).overflowY),
          ).length,
      ),
  ).toBe(0);
  const card = page.locator('.trace-attempt[data-trial="9"]');
  await card.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".trace-dialog")).toBeVisible();
  await expect(page.locator(".trace-dialog")).toContainText(
    "Separate initial overlap calculation",
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".trace-dialog")).toHaveCount(0);
  await expect(card).toBeFocused();
  await openChat(page);
  await page.locator("textarea").fill("收起后保留草稿");
  await page.getByRole("button", { name: "收起对话", exact: true }).click();
  await page.getByRole("tab", { name: "规格", exact: true }).click();
  await expect(page.locator(".chat-dialog")).not.toBeVisible();
  await openChat(page);
  await expect(page.locator("textarea")).toHaveValue("收起后保留草稿");
});
