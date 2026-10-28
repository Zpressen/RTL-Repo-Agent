import { openChat } from "../fixtures/studio";
import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";
test("removed RSI keeps engineering selection and independent visitors", async ({
  browser,
}) => {
  const a = await browser.newContext(),
    b = await browser.newContext();
  const p = await a.newPage(),
    q = await b.newPage();
  await offline(p);
  await offline(q);
  await p.goto(
    "/?case=e203&validation_id=e203-demo-v1-trial5&panel=verify&story_id=obsolete#/experience",
  );
  await openChat(p);
  await expect(p).toHaveURL(/#\/workspace$/);
  await expect(p.locator(".sample-metric")).toContainText("1 / 222");
  await p.locator("textarea").fill("visitor-a-private-draft");
  await q.goto("/?case=e203#/experience");
  await openChat(q);
  await expect(q.locator("textarea")).toHaveValue("");
  await p.reload();
  await openChat(p);
  await expect(p.locator("textarea")).toHaveValue("visitor-a-private-draft");
  await a.close();
  await b.close();
});
