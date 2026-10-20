import { expect, test } from "@playwright/test";

test("login, start S02, inspect released evidence, pause and resume on responsive screens", async ({
  page,
}) => {
  test.setTimeout(120000);
  const email = `runner-${Date.now()}@example.test`;
  const password = `Test-only-${Date.now()}-password`;
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Browser Runner");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(
    page.getByText("สมัครสำเร็จ กรุณาเข้าสู่ระบบด้วยบัญชีของคุณ"),
  ).toBeVisible();
  await page.getByRole("link", { name: "ไปเข้าสู่ระบบ" }).click();
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  await page.goto("/runs");
  await expect(
    page.getByRole("heading", { name: "รอบฝึกของฉัน" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "เริ่มรอบฝึก" })).toBeEnabled();
  await page.getByRole("button", { name: "เริ่มรอบฝึก" }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  await expect(
    page.getByRole("heading", { name: "สำรวจเหตุการณ์" }),
  ).toBeVisible();
  const runId = new URL(page.url()).pathname.split("/").at(-1);
  expect(runId).toBeTruthy();
  // Pause while the run is certainly active; waiting for investigation output
  // can outlast the short simulated run and make this control disappear.
  await expect(page.getByRole("button", { name: "พักรอบ" })).toBeVisible();
  const pauseResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith(`/runs/${runId}/pause`),
  );
  await page.getByRole("button", { name: "พักรอบ" }).click();
  const paused = await pauseResponse;
  expect(paused.status()).toBe(200);
  expect((await paused.json()).data.status).toBe("paused");
  await expect(page.getByRole("button", { name: "ทำต่อ" })).toBeVisible({
    timeout: 15000,
  });
  await page.reload();
  await expect(page.getByRole("button", { name: "ทำต่อ" })).toBeVisible();
  await page.getByRole("button", { name: "ทำต่อ" }).click();
  await expect(
    page
      .locator("section[aria-labelledby='alerts-title'] .run-list li")
      .first(),
  ).toBeVisible({ timeout: 50000 });
  await expect(
    page.locator("section[aria-labelledby='alerts-title'] a").first(),
  ).toBeVisible();
  const mockAnalysis = page
    .locator("section[aria-labelledby='tickets-title'] .run-list li")
    .filter({
      hasText: `mode=${process.env.SOC_AI_PROVIDER === "gemini_free" ? "real" : "mock"}`,
    });
  await expect(mockAnalysis.first()).toContainText("succeeded", {
    timeout: 50000,
  });
  await expect(mockAnalysis.first()).toContainText(
    `mode=${process.env.SOC_AI_PROVIDER === "gemini_free" ? "real" : "mock"}`,
  );
  await expect
    .poll(() => page.locator(".event-list button").count(), { timeout: 20000 })
    .toBeGreaterThan(0);
  await page.locator(".event-list button").first().click();
  await expect(page.getByRole("heading", { name: "Request" })).toBeVisible();
  await page.getByLabel("Asset", { exact: true }).fill("PORTAL-01");
  await expect
    .poll(() => page.locator(".event-list button").count())
    .toBeGreaterThan(0);
  await page.locator(".event-list button").first().click();
  await page.reload();
  await expect(page.getByLabel("Asset", { exact: true })).toHaveValue(
    "PORTAL-01",
  );
  await expect(page.getByRole("heading", { name: "Request" })).toBeVisible();
  await page.getByLabel("Asset", { exact: true }).fill("");
  await expect
    .poll(() => page.locator(".event-list button").count())
    .toBeGreaterThan(0);
  await page.locator(".event-list button").first().click();
  await expect(page.getByRole("heading", { name: "Response" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Log" })).toBeVisible();
  await page.reload();
  await expect(page.locator(".event-list button").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Request" })).toBeVisible();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});
