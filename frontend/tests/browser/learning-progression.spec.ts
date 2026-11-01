import { expect, test } from "@playwright/test";

const levelId = "15000000-0000-4000-8000-000000000001";
const lessonId = "15000000-0000-4000-8000-000000000101";

for (const passed of [1, 3]) {
  test(`passed ${passed}/3 attempts: show remaining exam or completed level truthfully`, async ({ page }) => {
    await page.route("**/api/v1/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown;
      if (path.endsWith("/auth/session")) data = { csrf_token: "test-only", user: { id: levelId, role: "analyst", display_name: "Learner", email: "learner@example.test", status: "active" }, expires_at: "2099-01-01T00:00:00Z" };
      else if (path.endsWith("/me/learning-path")) data = { lessons: [{ lesson_id: lessonId, lesson_version: 1, completed_steps: ["intro"], completed_at: "2026-10-01T00:00:00Z", version: 2 }], next_action: "continue_lesson", level_statuses: [{ level_id: levelId, unlocked: true, all_lessons_completed: true, exam_case_count: 3, passed_case_count: passed }] };
      else if (path.endsWith("/learning-path")) data = { levels: [{ id: levelId, ordinal: 1, title: "เริ่มต้น", lessons: [{ id: lessonId, title: "พื้นฐาน", version: 1 }] }] };
      else if (path.includes("/lessons/")) data = { id: lessonId, level_id: levelId, version: 1, title: "พื้นฐาน", steps: [{ id: "intro", title: "หลักฐาน", target: "GET /training", explanation: "อ่านหลักฐาน", limitation: "ยังไม่รู้ผลกระทบ" }] };
      else if (path.endsWith("/latest/result")) data = { attempt_id: levelId, status: "passed", score: 8, maximum: 8, criteria: [] };
      else return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
      return route.fulfill({ json: { data } });
    });
    await page.goto("/learning");
    await expect(page.getByText(`สอบผ่าน ${passed} / 3 ครั้ง`, { exact: true })).toBeVisible();
    if (passed === 1) await expect(page.getByRole("button", { name: "เริ่ม attempt ถัดไป", exact: true })).toBeEnabled();
    else {
      await expect(page.getByText("ผ่านข้อสอบครบตามจำนวนครั้งของระดับนี้แล้ว", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "เริ่ม attempt ถัดไป", exact: true })).toHaveCount(0);
    }
    for (const width of [375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  });
}
