import { test, expect } from "@playwright/test";
import { offline } from "../fixtures/studio";

for (const [cid, trial, total, phrase] of [
  ["e203", 20, 39, "低位部分状态"],
  ["aes_cipher_system_hard", 8, 8, "时钟边沿采样复位"],
  ["aes_inv_cipher_top_system", 4, 4, "重叠 kld"],
  ["sdc_controller_system", 17, 17, "错误的更新边沿"],
] as const) {
  test(`${cid} separates pre-fix diagnosis/code from its later patch and waveform`, async ({
    page,
  }) => {
    await offline(page);
    await page.goto("/?case=" + cid);
    await page.locator('.timeline-step[data-step="diagnose"]').click();
    await expect(page.locator(".timeline-step.active")).toContainText(
      "根因定位",
    );
    await expect(page.locator(".agent-trace .trace-attempt")).toHaveCount(
      total,
    );
    await page.locator(`.trace-attempt[data-trial="${trial}"]`).click();
    const diagnosis = page.locator(".history-diagnosis");
    await expect(diagnosis).toContainText(phrase);
    await expect(diagnosis.locator(".diagnosis-source")).not.toBeEmpty();
    await expect(diagnosis.locator(".diff-source")).toHaveCount(0);
    await expect(
      diagnosis.getByRole("button", { name: "本次候选波形", exact: true }),
    ).toHaveCount(0);
    await expect(page.locator(".agent-trace")).not.toContainText(
      "查看本次代码与波形",
    );
    await diagnosis.locator(".diagnosis-original summary").click();
    await expect(diagnosis.locator(".diagnosis-original")).toContainText(
      "SHA-256",
    );
    await page.reload();
    await expect(page.locator(".history-diagnosis")).toHaveAttribute(
      "data-trial",
      String(trial),
    );
    await page
      .getByRole("button", { name: "查看该次自动修复 ↗", exact: true })
      .click();
    await expect(page.locator(".history-repair")).toHaveAttribute(
      "data-trial",
      String(trial),
    );
    await expect(page.locator(".diff-source")).toContainText("@@ -");
    await expect(
      page.getByRole("button", { name: "本次候选波形", exact: true }),
    ).toBeVisible();
  });
}

test("a goal without a recorded diagnosis stays missing, and diagnosis downloads its baseline", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=e203");
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await page.locator('.trace-attempt[data-trial="39"]').click();
  await expect(page.locator(".history-diagnosis")).toContainText(
    "本次根因判断未记录",
  );
  await expect(
    page.locator(".history-diagnosis .diagnosis-source"),
  ).toHaveCount(0);
  await expect(page.locator(".history-diagnosis")).not.toContainText(
    "Separate initial overlap",
  );
  const manifest = await (
    await page.request.get("/cases/e203/manifest.json")
  ).json();
  const attempt = manifest.debug_history.runs[1].attempts[8];
  const url =
    manifest.evidence_packages.single[attempt.before_validation_id].url;
  const request = page.waitForRequest((r) => new URL(r.url()).pathname === url);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载证据包", exact: true }).click();
  await request;
  await download;
});

test("unverified AES edits keep the hypothesis without borrowing a simulation", async ({
  page,
}) => {
  await offline(page);
  await page.goto("/?case=aes_inv_cipher_top_system");
  await page.locator('.timeline-step[data-step="diagnose"]').click();
  await page.locator('.trace-attempt[data-trial="2"]').click();
  await expect(page.locator(".history-diagnosis")).toContainText(
    "data_load_accept",
  );
  await page.locator(".diagnosis-evidence summary").click();
  await expect(page.locator(".diagnosis-evidence")).toContainText(
    "没有单独完成仿真",
  );
  await expect(page.locator(".diagnosis-evidence .wave-canvas")).toHaveCount(0);
});
