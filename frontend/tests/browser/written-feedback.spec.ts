import { expect, test } from "@playwright/test";

const level = "15000000-0000-4000-8000-000000000001";
const submission = "15000000-0000-4000-8000-000000000002";
const questions = Array.from({ length: 10 }, (_, index) => ({
  id: `15000000-0000-4000-8000-${String(index + 3).padStart(12, "0")}`,
  ordinal: index + 1,
  prompt: `คำถาม ${index + 1}`,
  version: 1,
  category: "evidence",
}));

test("written feedback uses one grade request after frozen submit and escapes response", async ({ page }) => {
  let requested = false;
  let posts = 0;
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session")) return route.fulfill({ json: { data: {
      csrf_token: "test-only", user: { id: level, role: "analyst", display_name: "Learner", status: "active" },
      expires_at: "2099-01-01T00:00:00Z",
    } } });
    if (path.endsWith("/auth/csrf")) return route.fulfill({ json: { data: { csrf_token: "test-only" } } });
    if (path.endsWith("/learning-path")) return route.fulfill({ json: { data: { levels: [{ id: level, ordinal: 1, title: "เริ่มต้น" }] } } });
    if (path.endsWith("/written-questions")) return route.fulfill({ json: { data: questions } });
    if (path.endsWith("/written-submissions")) return route.fulfill({ json: { data: [{
      id: submission, level_id: level, status: "needs_review", created_at: "2026-10-29T00:00:00Z",
      questions, answers: questions.map((question) => ({ question_id: question.id, answer: "คำตอบของผู้เรียน" })),
    }] } });
    if (path.endsWith("/feedback")) {
      if (route.request().method() === "POST") {
        posts++;
        expect(route.request().postDataJSON()).toEqual({});
        expect(route.request().headers()["x-csrf-token"]).toBe("test-only");
        requested = true;
        return route.fulfill({ status: 202, json: { data: { status: "queued", result: null } } });
      }
      return requested
        ? route.fulfill({ json: { data: { status: "succeeded", result: { items: [{
          question_id: questions[0].id, verdict: "insufficient",
          explanation: "ตรวจเพิ่ม <img src=x onerror=alert(1)> SOC-003", section_ids: ["SOC-003"],
        }] } } } })
        : route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
    }
    return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
  });
  await page.goto("/knowledge-check");
  await page.getByText(/needs_review — รอประเมิน/).click();
  await page.getByRole("button", { name: "ให้ AI ตรวจคำตอบ" }).click();
  await expect(page.getByText(/ตรวจเพิ่ม/)).toBeVisible();
  await expect(page.locator("img")).toHaveCount(0);
  expect(posts).toBe(1);
  await expect(page.getByRole("region", { name: "ข้อเสนอแนะจาก AI" })
    .getByText(/ไม่ใช่คะแนนสอบหรือการปลดล็อกระดับ/)).toBeVisible();
});
