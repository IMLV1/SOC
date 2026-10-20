import { expect, test } from "@playwright/test";

test("lesson progress is saved on the server, resumes after refresh, and stays usable on mobile/tablet/desktop", async ({
  page,
}) => {
  const email = `learning-${Date.now()}@example.test`;
  const password = `Test-only-${Date.now()}-password`;

  await page.goto("/learning");
  await expect(
    page.getByRole("heading", { name: "เข้าสู่ระบบเพื่ออ่านบทเรียน" }),
  ).toBeVisible();
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Learning Analyst");
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
  await expect(page.getByText(email, { exact: true })).toBeVisible();

  await page.goto("/learning");
  await expect(page.getByText("ขั้น 1 / 5")).toBeVisible();
  await page.getByRole("button", { name: "ทำขั้นนี้เสร็จ" }).click();
  await expect(page.getByText("ขั้น 2 / 5")).toBeVisible();
  await page.reload();
  await expect(page.getByText("เรียนแล้ว 1 จาก 5 ขั้น")).toBeVisible();
  await expect(page.getByText("ขั้น 2 / 5")).toBeVisible();

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }

  for (let step = 2; step <= 5; step += 1) {
    await expect(page.getByText(`ขั้น ${step} / 5`)).toBeVisible();
    await page.getByRole("button", { name: "ทำขั้นนี้เสร็" }).click();
  }
  await expect(page.getByText("ครบทุกขั้นแล้ว")).toBeVisible();
  await page.getByRole("button", { name: "จบบทเรียนและบันทึก" }).click();
  await expect(page.getByText("จบบทเรียนแล้ว")).toBeVisible();
  await expect(page.getByRole("button", { name: "เริ่มข้อสอบระดับนี้" })).toBeVisible();

  await page.getByRole("button", { name: "เริ่มข้อสอบระดับนี้" }).click();
  await expect(page.getByRole("heading", { name: "Investigation case" })).toBeVisible();
  await page.getByRole("checkbox").first().check();
  await page.getByLabel("เหตุผลและการวิเคราะห์").fill(
    "The request and response events provide the evidence for this assessment.",
  );
  await page.getByRole("button", { name: "ส่งข้อสอบ" }).click();
  await expect(page.getByText("ผลข้อสอบ: needs_review")).toBeVisible();
  await expect(page.getByText("ส่งคำตอบแล้ว รอ Instructor ตรวจ ไม่มีการประเมินผ่านอัตโนมัติ")).toBeVisible();

  // Model a later Instructor decision and verify the retake screen can be
  // recovered after refresh without altering the backend-owned exam result.
  await page.route("**/api/v1/exam/attempts/active", (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: { code: "NOT_FOUND" } }) }),
  );
  await page.route("**/api/v1/exam/attempts/latest/result", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: { attempt_id: "16000000-0000-4000-8000-000000000001", status: "failed", score: 4, maximum: 10, criteria: [] } }) }),
  );
  await page.route("**/api/v1/learning/levels/*/attempts", (route) =>
    route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ data: { id: "16000000-0000-4000-8000-000000000002", level_id: "15000000-0000-4000-8000-000000000001", status: "in_progress", version: 1, expires_at: new Date(Date.now() + 3600000).toISOString(), events: [{ id: "16000000-0000-4000-8000-000000000003", release_seq: 1, event_time: new Date().toISOString(), source: "proxy", asset_id: "web-01", username: null, src_ip: null, request: null, response: null, log: {} }], answer: null }, meta: { request_id: "browser-retake" } }) }),
  );
  await page.reload();
  await expect(page.getByText("ผลข้อสอบ: failed")).toBeVisible();
  await expect(page.getByRole("button", { name: "เริ่ม attempt ถัดไป" })).toBeVisible();
  await page.getByRole("button", { name: "เริ่ม attempt ถัดไป" }).click();
  await expect(page.getByRole("heading", { name: "Investigation case" })).toBeVisible();

  const path = await (await page.request.get("/api/v1/me/learning-path")).json();
  expect(path.data.lessons[0].completed_steps).toHaveLength(5);
  expect(path.data.lessons[0].completed_at).not.toBeNull();
  expect(path.data.next_action).toBe("review_lesson_exam_unavailable");
});
