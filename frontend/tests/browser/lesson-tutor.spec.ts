import { expect, test } from "@playwright/test";

const level = "15000000-0000-4000-8000-000000000001";
const lesson = "15000000-0000-4000-8000-000000000101";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith("/auth/session")) data = { csrf_token: "test-only", user: { id: level, role: "analyst", display_name: "Learner", status: "active" }, expires_at: "2099-01-01T00:00:00Z" };
    else if (path.endsWith("/me/learning-path")) data = { lessons: [], next_action: "continue_lesson" };
    else if (path.endsWith("/learning-path")) data = { levels: [{ id: level, ordinal: 1, title: "เริ่มต้น", lessons: [{ id: lesson, title: "พื้นฐาน", version: 1 }] }] };
    else if (path.includes("/lessons/")) data = { id: lesson, level_id: level, version: 1, title: "พื้นฐาน", steps: [{ id: "intro", title: "หลักฐาน", target: "GET /training", explanation: "อ่านหลักฐาน", limitation: "ยังไม่รู้ผลกระทบ" }] };
    else return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
    return route.fulfill({ json: { data } });
  });
});

test("tutor preserves unsent question, polls durable result, escapes content and reloads history", async ({ page }) => {
  let fail = true;
  let submitted = false;
  let polls = 0;
  const keys: string[] = [];
  await page.route("**/api/v1/tutor/availability", (route) => route.fulfill({ json: { data: { available: true, reason: null } } }));
  const record = { id: level, lesson_id: lesson, question: "HTTP 403 <sample> คืออะไร", status: "queued", result: null };
  await page.route("**/api/v1/tutor/questions", (route) => {
    if (route.request().method() === "POST") {
      keys.push(route.request().headers()["idempotency-key"]);
      expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
      expect(route.request().postDataJSON().lesson_id).toBe(lesson);
      if (fail) return route.fulfill({ status: 503, json: { error: { code: "SERVICE_UNAVAILABLE" } } });
      submitted = true;
      return route.fulfill({ status: 202, json: { data: record } });
    }
    polls++;
    return route.fulfill({ json: { data: !submitted ? [] : [{ ...record, status: "succeeded", result: { answer: "ไม่ยืนยันข้อมูลรั่ว <img src=x onerror=alert(1)> SOC-003", sources: [{ title: "คู่มือ", excerpt: "SOC-003 อ่าน response", section_ids: ["SOC-003"] }] } }] } });
  });
  await page.goto("/learning");
  const tutor = page.getByRole("region", { name: "ถามผู้ช่วยสอน AI" });
  const input = tutor.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill(record.question);
  await tutor.getByRole("button", { name: "ส่งคำถาม", exact: true }).click();
  await expect(tutor.getByRole("alert")).toContainText("เก็บข้อความไว้แล้ว");
  await expect(input).toHaveValue(record.question);
  fail = false;
  await tutor.getByRole("button", { name: "ส่งคำถาม", exact: true }).click();
  await expect(tutor.getByText(/ไม่ยืนยันข้อมูลรั่ว/)).toBeVisible();
  expect(keys[0]).toBe(keys[1]);
  await expect(tutor.locator("img, sample")).toHaveCount(0);
  await page.reload();
  await expect(tutor.getByText(record.question, { exact: true })).toBeVisible();
  expect(polls).toBeGreaterThan(1);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

for (const reason of ["DIFY_RELEASE_NOT_APPROVED", "EXAM_ATTEMPT_ACTIVE"]) {
  test(`unavailable tutor is truthful and cannot dispatch: ${reason}`, async ({ page }) => {
    let posts = 0;
    await page.route("**/api/v1/tutor/availability", (route) => route.fulfill({ json: { data: { available: false, reason } } }));
    await page.route("**/api/v1/tutor/questions", (route) => { if (route.request().method() === "POST") posts++; return route.fulfill({ json: { data: [] } }); });
    await page.goto("/learning");
    const tutor = page.getByRole("region", { name: "ถามผู้ช่วยสอน AI" });
    await expect(tutor.getByRole("status")).toContainText(reason === "EXAM_ATTEMPT_ACTIVE" ? "ปิดระหว่าง" : "รอรับรอง");
    await expect(tutor.getByRole("button", { name: "ส่งคำถาม", exact: true })).toBeDisabled();
    expect(posts).toBe(0);
  });
}
