import { expect, test } from "@playwright/test";

const attemptId = "26000000-0000-4000-8000-000000000001";
const levelId = "15000000-0000-4000-8000-000000000001";

function envelope(data: unknown) {
  return { status: 200, contentType: "application/json", body: JSON.stringify({ data }) };
}

test("Instructor reviews a submitted exam and learner sees the saved feedback", async ({ page }) => {
  const user = {
    id: "26000000-0000-4000-8000-000000000002",
    display_name: "Assigned Instructor",
    email: "instructor@example.test",
    role: "instructor",
    status: "active",
  };
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill(envelope({ csrf_token: "browser-csrf", user, expires_at: new Date(Date.now() + 3600000).toISOString() })),
  );
  await page.route("**/api/v1/admin/exam-attempts", (route) =>
    route.fulfill(envelope([{ id: attemptId, owner_user_id: "26000000-0000-4000-8000-000000000003", display_name: "Learner One", level_id: levelId, status: "needs_review", version: 2, submitted_at: new Date().toISOString() }])),
  );
  await page.route(`**/api/v1/admin/exam-attempts/${attemptId}`, (route) =>
    route.fulfill(envelope({
      attempt: { id: attemptId, status: "needs_review", version: 2 },
      events: [{ id: "26000000-0000-4000-8000-000000000004", release_seq: 1, event_time: "2026-10-20T00:00:00Z", source: "proxy", asset_id: "web-01", username: null, src_ip: null, request: { method: "GET", path: "/login" }, response: { status: 401 }, log: {} }],
      answer: { evidence_event_ids: ["26000000-0000-4000-8000-000000000004"], severity: "medium", disposition: "true_positive", reason: "Evidence shows repeated failed authentication." },
      private_truth: { expectedEvidenceKeys: ["auth-failure"], expectedSeverity: "medium", expectedDisposition: "true_positive", criterionGuidance: { analysis: "Explain how the events support the conclusion." } },
    })),
  );
  await page.route(`**/api/v1/admin/exam-attempts/${attemptId}/review`, async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(await route.request().postDataJSON()).toEqual({ expected_version: 2, criterion_scores: { analysis: 2, reasoning: 1 }, reason: "Evidence and analysis support the classification." });
    await route.fulfill(envelope({ attempt_id: attemptId, status: "passed", score: 7, maximum: 8, criteria: [
      { key: "evidence", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "analysis", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "classification", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "reasoning", score: 1, maximum: 2, feedback: "มีส่วนที่ทำได้ ควรทบทวนเกณฑ์นี้" },
    ] }));
  });

  await page.goto("/instructor/exams");
  await page.getByRole("link", { name: "Learner One · needs_review" }).click();
  await expect(page.getByRole("heading", { name: "ตรวจคำตอบข้อสอบ" })).toBeVisible();
  await expect(page.getByText("Evidence shows repeated failed authentication.")).toBeVisible();
  await expect(page.getByText("Evidence keys: auth-failure")).toBeVisible();
  await page.getByLabel("analysis").selectOption("2");
  await page.getByLabel("reasoning").selectOption("1");
  await page.getByLabel("เหตุผลการตรวจ").fill("Evidence and analysis support the classification.");
  await page.getByRole("button", { name: "บันทึกผลตรวจ" }).click();
  await expect(page.getByRole("heading", { name: "ผล: passed" })).toBeVisible();
  await expect(page.getByText("คะแนน 7/8")).toBeVisible();

  const learnerPage = await page.context().newPage();
  await learnerPage.route("**/api/v1/learning-path", (route) => route.fulfill(envelope({
    levels: [{ id: levelId, ordinal: 1, title: "พื้นฐาน", lessons: [{
      id: "15000000-0000-4000-8000-000000000101", version: 1, title: "พื้นฐานการสืบสวน",
    }] }],
  })));
  await learnerPage.route("**/api/v1/auth/session", (route) =>
    route.fulfill(envelope({ csrf_token: "learner-csrf", user: { ...user, id: "26000000-0000-4000-8000-000000000003", display_name: "Learner One", email: "learner@example.test", role: "analyst" }, expires_at: new Date(Date.now() + 3600000).toISOString() })),
  );
  await learnerPage.route("**/api/v1/lessons/*", (route) => route.fulfill(envelope({
    id: "15000000-0000-4000-8000-000000000101", level_id: levelId, version: 1, title: "พื้นฐานการสืบสวน", steps: [{ id: "intro", title: "เริ่มต้น", target: "GET /login", explanation: "ตรวจ request และ response", limitation: "เหตุการณ์เดียวไม่ยืนยันผลกระทบ" }],
  })));
  await learnerPage.route("**/api/v1/me/learning-path", (route) => route.fulfill(envelope({ lessons: [{ lesson_id: "15000000-0000-4000-8000-000000000101", lesson_version: 1, completed_steps: ["intro"], completed_at: new Date().toISOString(), version: 2 }], next_action: "continue_lesson" })));
  await learnerPage.route("**/api/v1/exam/attempts/active", (route) => route.fulfill(envelope({
    id: attemptId, level_id: levelId, status: "needs_review", version: 3, expires_at: new Date(Date.now() + 3600000).toISOString(), events: [], answer: null,
  })));
  await learnerPage.route(`**/api/v1/exam/attempts/${attemptId}/result`, (route) => route.fulfill(envelope({
    attempt_id: attemptId, status: "passed", score: 7, maximum: 8, criteria: [
      { key: "evidence", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "analysis", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "classification", score: 2, maximum: 2, feedback: "ทำได้ตามเกณฑ์" },
      { key: "reasoning", score: 1, maximum: 2, feedback: "มีส่วนที่ทำได้ ควรทบทวนเกณฑ์นี้" },
    ],
  })));
  await learnerPage.goto("/learning");
  await expect(learnerPage.getByText("ผลข้อสอบ: passed")).toBeVisible();
  await expect(learnerPage.getByText("คะแนนประกอบการฝึก 7/8", { exact: true })).toBeVisible();
  await expect(learnerPage.getByText("มีส่วนที่ทำได้ ควรทบทวนเกณฑ์นี้")).toBeVisible();
});
