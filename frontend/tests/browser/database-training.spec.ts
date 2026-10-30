import { expect, test } from "@playwright/test";

const caseId = "22000000-0000-4000-8000-000000000001";
const eventId = "22000000-0000-4000-8000-000000000002";
const levelId = "15000000-0000-4000-8000-000000000001";
const summary = { id: caseId, stable_key: "TR-L1-01", level_id: levelId, level: 1, category: "authentication", title: "ตรวจหลักฐานการเข้าสู่ระบบ", version: 1, available: true };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({ json: { data: {
    csrf_token: "test-only", expires_at: "2099-01-01T00:00:00Z",
    user: { id: "22000000-0000-4000-8000-000000000003", role: "analyst", display_name: "Learner", status: "active", email: "learner@example.test" },
  } } }));
});

test("practice uses API drafts/history across refresh, escapes logs and keeps draft after conflict", async ({ page }) => {
  let draft: Record<string, unknown> | null = null;
  let version = 0;
  let conflict = false;
  const history: unknown[] = [];
  await page.route("**/api/v1/practice/ai-availability", (route) => route.fulfill({ json: { data: { available: false } } }));
  await page.route(`**/api/v1/practice/cases/${caseId}/ai-questions`, (route) => route.fulfill({ json: { data: [] } }));
  await page.route("**/api/v1/practice/cases", (route) => route.fulfill({ json: { data: [summary] } }));
  await page.route(`**/api/v1/practice/cases/${caseId}`, (route) => route.fulfill({ json: { data: {
    ...summary, prompt: "อ่านข้อมูลก่อนสรุป", draft, draft_version: version, draft_saved_at: "2026-01-01T00:00:00Z",
    events: [{ id: eventId, time: "2026-01-01T00:00:00Z", source: "authentication", asset: "TRAIN", username: "learner", src_ip: "192.0.2.1", request: { path: "/training/<sample>" }, response: { status: 401 }, log: { message: "<img src=x onerror=alert(1)>" } }],
  } } }));
  await page.route(`**/api/v1/practice/cases/${caseId}/draft`, async (route) => {
    const body = route.request().postDataJSON();
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(body.expected_version).toBe(version);
    if (conflict) return route.fulfill({ status: 409, json: { error: { code: "VERSION_CONFLICT" } } });
    draft = body.answer; version += 1;
    return route.fulfill({ json: { data: { ...summary, prompt: "อ่านข้อมูลก่อนสรุป", events: [], draft, draft_version: version } } });
  });
  await page.route(`**/api/v1/practice/cases/${caseId}/answers`, async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { data: history } });
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    const result = { id: "22000000-0000-4000-8000-000000000004", case_id: caseId, case_version: 1, created_at: "2026-10-22T01:00:00Z", answer: route.request().postDataJSON(), feedback: {
      mode: "deterministic", classification_correct: false, evidence_correct: true, expected_severity: "medium", expected_disposition: "true_positive", explanation: "พบการลองรหัสซ้ำ แต่ยังไม่พบ session สำเร็จ", limitation: "ยังไม่ยืนยัน compromise", reason_review_message: "ยังไม่ประเมินความหมายจนกว่าจะเชื่อม Dify", is_exam_result: false,
    } };
    history.push(result);
    return route.fulfill({ status: 201, json: { data: result } });
  });
  await page.goto("/demo/learning?view=practice");
  await expect(page).toHaveURL(/\/practice\?case=/);
  await expect(page.locator(".practice-event pre")).toContainText("/training/<sample>");
  await expect(page.locator("sample, img[src=x]")).toHaveCount(0);
  await page.getByRole("checkbox").check();
  const reason = page.getByLabel("เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ");
  await reason.fill("เลือกหลักฐานที่มีในเคส และยังต้องตรวจผลกระทบ");
  await page.getByRole("button", { name: "บันทึกร่าง", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("บันทึกร่างในบัญชีแล้ว");
  await page.reload();
  await expect(reason).toHaveValue("เลือกหลักฐานที่มีในเคส และยังต้องตรวจผลกระทบ");
  conflict = true;
  await reason.fill("ร่างใหม่ที่ต้องไม่หายเมื่อ conflict");
  await page.getByRole("button", { name: "บันทึกร่าง", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("ร่างของคุณยังอยู่");
  await expect(reason).toHaveValue("ร่างใหม่ที่ต้องไม่หายเมื่อ conflict");
  await page.getByRole("button", { name: "ส่งคำตอบและตรวจข้อสรุป" }).click();
  await expect(page.getByRole("heading", { name: "ผลตรวจคำตอบล่าสุด" })).toBeVisible();
  await expect(page.locator(".practice-incorrect")).toContainText("ยังไม่ถูก");
  await page.reload();
  await expect(reason).toHaveValue("ร่างใหม่ที่ต้องไม่หายเมื่อ conflict");
  await expect(page.getByRole("heading", { name: "ประวัติคำตอบ · 1" })).toBeVisible();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test("practice requires a real session and never falls back to JSON", async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } }));
  await page.goto("/practice");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบเพื่อฝึกและบันทึกคำตอบ" })).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(0);
});

test("practice Ask AI unlocks after submission and restores the queued question", async ({ page }) => {
  const answerId = "22000000-0000-4000-8000-000000000004";
  const questionId = "22000000-0000-4000-8000-000000000005";
  const questions: unknown[] = [];
  let answers: unknown[] = [];
  await page.route("**/api/v1/practice/cases", (route) => route.fulfill({ json: { data: [summary] } }));
  await page.route(`**/api/v1/practice/cases/${caseId}`, (route) => route.fulfill({ json: { data: {
    ...summary, prompt: "อ่านหลักฐาน", draft: null, draft_version: 0, draft_saved_at: null,
    events: [{ id: eventId, time: "2026-01-01T00:00:00Z", source: "web", asset: "TRAIN", username: "learner", src_ip: "192.0.2.1", request: { path: "/admin" }, response: { status: 403 }, log: {} }],
  } } }));
  await page.route("**/api/v1/practice/ai-availability", (route) => route.fulfill({ json: { data: { available: true } } }));
  await page.route(`**/api/v1/practice/cases/${caseId}/answers`, (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { data: answers } });
    const answer = { id: answerId, case_id: caseId, case_version: 1, created_at: "2026-10-30T01:00:00Z", answer: route.request().postDataJSON(), feedback: {
      mode: "deterministic", classification_correct: true, evidence_correct: true,
      expected_severity: "low", expected_disposition: "undetermined", explanation: "ต้องตรวจเพิ่ม",
      limitation: "ยังไม่ทราบผลกระทบ", reason_review_message: "AI ไม่เปลี่ยนผลตรวจ", is_exam_result: false,
    } };
    answers = [answer];
    return route.fulfill({ status: 201, json: { data: answer } });
  });
  await page.route(`**/api/v1/practice/cases/${caseId}/ai-questions`, (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { data: questions } });
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    expect(route.request().postDataJSON().answer_id).toBe(answerId);
    const question = { id: questionId, case_id: caseId, answer_id: answerId, question: "403 ยืนยันข้อมูลรั่วไหม", status: "queued", result: null, error_code: null, created_at: "2026-10-30T01:01:00Z" };
    questions.push(question);
    return route.fulfill({ status: 202, json: { data: question } });
  });
  await page.goto("/practice");
  await expect(page.getByRole("button", { name: "ถาม AI", exact: true })).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.getByLabel("เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ").fill("403 ยังไม่ยืนยันข้อมูลรั่ว");
  await page.getByRole("button", { name: "ส่งคำตอบและตรวจข้อสรุป" }).click();
  await page.getByLabel("คำถามของคุณ").fill("403 ยืนยันข้อมูลรั่วไหม");
  await page.getByRole("button", { name: "ถาม AI", exact: true }).click();
  await expect(page.getByRole("heading", { name: "403 ยืนยันข้อมูลรั่วไหม" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "403 ยืนยันข้อมูลรั่วไหม" })).toBeVisible();
});

test("written knowledge check sends all ten answers once and restores immutable history", async ({ page }) => {
  const questions = Array.from({ length: 10 }, (_, index) => ({ id: `22000000-0000-4000-8000-${String(index + 10).padStart(12, "0")}`, ordinal: index + 1, version: 1, category: "written_knowledge", prompt: `อธิบายข้อจำกัดของหลักฐาน ข้อ ${index + 1}` }));
  const saved: unknown[] = [];
  await page.route("**/api/v1/learning-path", (route) => route.fulfill({ json: { data: { levels: [{ id: levelId, ordinal: 1, title: "เริ่มต้น" }] } } }));
  await page.route(`**/api/v1/learning/levels/${levelId}/written-questions`, (route) => route.fulfill({ json: { data: questions } }));
  await page.route(`**/api/v1/learning/levels/${levelId}/written-submissions`, async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { data: saved } });
    const payload = route.request().postDataJSON();
    expect(payload.answers).toHaveLength(10);
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    const result = { id: caseId, level_id: levelId, status: "needs_review", created_at: "2026-10-22T01:00:00Z", answers: payload.answers, questions };
    saved.push(result);
    return route.fulfill({ status: 201, json: { data: result } });
  });
  await page.goto("/knowledge-check");
  const submit = page.getByRole("button", { name: "ส่งคำตอบครบ 10 ข้อ" });
  await expect(submit).toBeDisabled();
  const fields = page.getByRole("textbox");
  await expect(fields).toHaveCount(10);
  for (let index = 0; index < 10; index += 1) await fields.nth(index).fill(`หลักฐานข้อ ${index + 1} ยังไม่ยืนยันผลกระทบ`);
  await submit.click();
  await expect(page.getByText(/needs_review — รอประเมิน ไม่ใช่สอบผ่าน/)).toBeVisible();
  await page.reload();
  await page.getByText(/needs_review — รอประเมิน ไม่ใช่สอบผ่าน/).click();
  await expect(page.getByText("หลักฐานข้อ 10 ยังไม่ยืนยันผลกระทบ", { exact: true })).toBeVisible();
});
