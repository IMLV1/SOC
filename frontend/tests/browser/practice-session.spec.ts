import { expect, test, type Page } from "@playwright/test";

const caseId = "22000000-0000-4000-8000-000000000001";
const eventId = "22000000-0000-4000-8000-000000000002";
const reasonLabel = "เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ";

async function mockPractice(page: Page) {
  const calls = { session: 0, practice: 0, user: "learner-a", authenticated: true };
  const summary = { id: caseId, stable_key: "TR-L1-01", level_id: caseId, level: 1,
    category: "authentication", title: "หลักฐานทดสอบ", version: 1, available: true };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith("/auth/session")) {
      calls.session++;
      if (!calls.authenticated) return route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } });
      data = { csrf_token: `test-${calls.session}`, expires_at: "2099-01-01T00:00:00Z",
        user: { id: calls.user, display_name: `Learner ${calls.session}`, role: "analyst", status: "active" } };
    } else {
      calls.practice++;
      if (path.endsWith("/practice/cases")) data = [summary];
      else if (path.endsWith(`/practice/cases/${caseId}`)) data = {
        ...summary, prompt: `หลักฐานของ ${calls.user}`, draft: null, draft_version: 0, draft_saved_at: null,
        events: [{ id: eventId, time: "2026-01-01T00:00:00Z", source: "web", asset: "TRAIN", src_ip: "192.0.2.1",
          request: { path: "/sample" }, response: { status: 403 }, log: {} }],
      };
      else if (path.endsWith("/answers")) data = [{ id: eventId, created_at: "2026-01-01T00:00:00Z",
        answer: { evidence_ids: [eventId], severity: "medium", disposition: "undetermined", reason: "คำตอบที่ส่งไว้" },
        feedback: { classification_correct: true, evidence_correct: true, expected_severity: "medium", expected_disposition: "undetermined" } }];
      else if (path.endsWith("/ai-questions")) data = [];
      else if (path.endsWith("/ai-availability")) data = { available: true };
      else return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
    }
    return route.fulfill({ json: { data } });
  });
  return calls;
}

test("same-account focus and minute refresh preserve mounted evidence, drafts and filters without refetch", async ({ page }) => {
  await page.clock.install();
  const calls = await mockPractice(page);
  await page.goto("/practice");
  const reason = page.getByLabel(reasonLabel);
  await reason.fill("ร่างที่กำลังอ่านและพิมพ์");
  await page.getByRole("textbox", { name: "คำถามของคุณ", exact: true }).fill("ร่างคำถาม AI");
  await page.getByRole("combobox", { name: /^ระดับ/ }).selectOption("1");
  await page.getByRole("combobox", { name: /^หมวด/ }).selectOption("authentication");
  const originalCalls = calls.practice;
  const originalInput = await reason.elementHandle();
  for (const trigger of ["focus", "minute"]) {
    const before = calls.session;
    if (trigger === "focus") await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    else await page.clock.fastForward(60000);
    await expect.poll(() => calls.session).toBeGreaterThan(before);
    await expect(page.getByRole("link", { name: `Learner ${calls.session}`, exact: true })).toBeVisible();
    await expect(reason).toHaveValue("ร่างที่กำลังอ่านและพิมพ์");
    expect(await originalInput!.evaluate((node) => node.isConnected)).toBe(true);
    await expect(page.getByRole("textbox", { name: "คำถามของคุณ", exact: true })).toHaveValue("ร่างคำถาม AI");
    await expect(page.getByRole("combobox", { name: /^ระดับ/ })).toHaveValue("1");
    await expect(page.getByRole("combobox", { name: /^หมวด/ })).toHaveValue("authentication");
    expect(calls.practice).toBe(originalCalls);
  }
});

test("switching accounts resets private drafts and loads the new account", async ({ page }) => {
  const calls = await mockPractice(page);
  await page.goto("/practice");
  await page.getByLabel(reasonLabel).fill("ร่างส่วนตัวของบัญชี A");
  await page.getByRole("textbox", { name: "คำถามของคุณ", exact: true }).fill("คำถามส่วนตัวของบัญชี A");
  calls.user = "learner-b";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByText("หลักฐานของ learner-b", { exact: true })).toBeVisible();
  await expect(page.getByLabel(reasonLabel)).toHaveValue("คำตอบที่ส่งไว้");
  await expect(page.getByRole("textbox", { name: "คำถามของคุณ", exact: true })).toHaveValue("");
});

test("expired session removes evidence and private drafts", async ({ page }) => {
  const calls = await mockPractice(page);
  await page.goto("/practice");
  await page.getByLabel(reasonLabel).fill("ร่างส่วนตัว");
  calls.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบเพื่อฝึกและบันทึกคำตอบ" })).toBeVisible();
  await expect(page.getByLabel(reasonLabel)).toHaveCount(0);
  await expect(page.locator(".practice-layout")).toHaveCount(0);
});
