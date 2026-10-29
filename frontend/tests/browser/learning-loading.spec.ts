import { expect, test, type Page } from "@playwright/test";

const level = "15000000-0000-4000-8000-000000000001";
const lessons = [101, 102, 103].map((id) => `15000000-0000-4000-8000-${String(id).padStart(12, "0")}`);

function gate() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}

async function mockLearning(page: Page, options: { exam?: Promise<void>; examFailure?: boolean; firstLesson?: Promise<void>; secondLesson?: Promise<void> } = {}) {
  const calls = { session: 0, lesson: 0, catalog: 0, tutor: 0, user: level, questionPending: true };
  let submitted = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith("/auth/session")) {
      calls.session++;
      data = { csrf_token: "test-only", user: { id: calls.user, role: "analyst", display_name: `Learner ${calls.session}`, status: "active" }, expires_at: "2099-01-01T00:00:00Z" };
    } else if (path.endsWith("/me/learning-path")) data = { lessons: [], next_action: "continue_lesson" };
    else if (path.endsWith("/learning-path")) {
      calls.catalog++;
      data = { levels: [{ id: level, ordinal: 1, title: "เริ่มต้น", lessons: lessons.map((id, index) => ({ id, version: 1, title: `บทเรียน ${index + 1}` })) }] };
    } else if (path.includes("/lessons/")) {
      calls.lesson++;
      const id = path.split("/").at(-1)!;
      if (id === lessons[0]) await options.firstLesson;
      if (id === lessons[1]) await options.secondLesson;
      data = { id, level_id: level, version: 1, title: `บทเรียน ${lessons.indexOf(id) + 1}`, steps: [{ id: "intro", title: "หลักฐาน", target: "GET /training", explanation: "อ่านหลักฐาน", limitation: "ยังไม่รู้ผลกระทบ" }] };
    } else if (path.endsWith("/tutor/availability")) {
      calls.tutor++;
      data = { available: true, reason: null };
    } else if (path.endsWith("/tutor/questions")) {
      const record = { id: level, lesson_id: lessons[0], question: "HTTP 403 คืออะไร", error_code: null,
        status: calls.questionPending ? "queued" : "succeeded",
        result: calls.questionPending ? null : { answer: "คำตอบจำลองจากงานเบื้องหลัง SOC-003", sources: [] } };
      if (route.request().method() === "POST") {
        submitted = true;
        return route.fulfill({ status: 202, json: { data: record } });
      }
      data = submitted ? [record] : [];
    }
    else {
      if (path.endsWith("/exam/attempts/active")) {
        await options.exam;
        if (options.examFailure) return route.fulfill({ status: 503, json: { error: { code: "SERVICE_UNAVAILABLE" } } });
      }
      return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } });
    }
    return route.fulfill({ json: { data } });
  });
  return calls;
}

test("same-account focus and minute timer preserve lesson and unsent AI draft without refetch", async ({ page }) => {
  await page.addInitScript(() => {
    const browser = window as unknown as {
      setInterval: (handler: TimerHandler, delay?: number, ...args: unknown[]) => number;
      clearInterval: (id?: number) => void;
      runMinuteTimers: () => void;
    };
    const callbacks = new Map<number, () => void>();
    const set = browser.setInterval.bind(window);
    const clear = browser.clearInterval.bind(window);
    browser.setInterval = (handler, delay, ...args) => {
      const id = set(handler, delay, ...args);
      if (delay === 60000 && typeof handler === "function") callbacks.set(id, () => handler(...args));
      return id;
    };
    browser.clearInterval = (id) => { if (id !== undefined) callbacks.delete(id); clear(id); };
    browser.runMinuteTimers = () => callbacks.forEach((run) => run());
  });
  const calls = await mockLearning(page);
  await page.goto("/learning");
  const input = page.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill("ร่างคำถามที่ยังไม่ส่ง");
  const original = { lesson: calls.lesson, catalog: calls.catalog, tutor: calls.tutor };
  for (const trigger of ["focus", "timer"]) {
    const before = calls.session;
    if (trigger === "focus") await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    else await page.evaluate(() => (window as unknown as { runMinuteTimers: () => void }).runMinuteTimers());
    await expect.poll(() => calls.session).toBeGreaterThan(before);
    await expect(page.getByRole("link", { name: `Learner ${calls.session}`, exact: true })).toBeVisible();
    await expect(input).toHaveValue("ร่างคำถามที่ยังไม่ส่ง");
    expect({ lesson: calls.lesson, catalog: calls.catalog, tutor: calls.tutor }).toEqual(original);
  }
});

test("AI job polling updates only the tutor, not the lesson", async ({ page }) => {
  const calls = await mockLearning(page);
  await page.goto("/learning");
  await page.getByLabel("คำถามเกี่ยวกับบทเรียน").fill("HTTP 403 คืออะไร");
  const original = calls.lesson;
  await page.getByRole("button", { name: "ส่งคำถาม", exact: true }).click();
  await expect(page.getByText("กำลังรอประมวลผล", { exact: true })).toBeVisible();
  calls.questionPending = false;
  await expect(page.getByText("คำตอบจำลองจากงานเบื้องหลัง SOC-003", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "บทเรียน 1", exact: true })).toBeVisible();
  expect(calls.lesson).toBe(original);
});

test("exam status failure preserves study content but blocks AI until verified again", async ({ page }) => {
  const options = { examFailure: false };
  await mockLearning(page, options);
  await page.goto("/learning");
  const input = page.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill("ร่างที่ต้องอยู่หลังตรวจสิทธิ์ใหม่");
  options.examFailure = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator("p[role='alert']")).toContainText("ตรวจสถานะสอบไม่สำเร็จ");
  await expect(page.getByRole("heading", { name: "บทเรียน 1", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ส่งคำถาม", exact: true })).toHaveCount(0);
  options.examFailure = false;
  await page.getByRole("button", { name: "ตรวจผลและสิทธิ์ล่าสุด", exact: true }).click();
  await expect(input).toHaveValue("ร่างที่ต้องอยู่หลังตรวจสิทธิ์ใหม่");
});

test("background progress refresh keeps the lesson, revealed evidence and AI draft mounted", async ({ page }) => {
  const refresh = gate();
  const options: { firstLesson?: Promise<void> } = {};
  await mockLearning(page, options);
  await page.goto("/learning");
  const input = page.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill("ยังพิมพ์ไม่จบ");
  await page.getByRole("button", { name: "กดดู: หลักฐาน", exact: false }).click();
  options.firstLesson = refresh.promise;
  try {
    const request = page.waitForRequest(`**/lessons/${lessons[0]}`);
    await page.getByRole("button", { name: "ตรวจผลและสิทธิ์ล่าสุด", exact: true }).click();
    await request;
    await expect(page.getByText("กำลังอัปเดตความคืบหน้า…", { exact: true })).toBeVisible();
    await expect(input).toHaveValue("ยังพิมพ์ไม่จบ");
    await expect(page.getByText("อ่านหลักฐาน", { exact: true })).toBeVisible();
  } finally { refresh.release(); }
  await expect(page.getByRole("button", { name: "ส่งคำถาม", exact: true })).toBeEnabled();
});

test("slow exam status does not block lesson content or grant early AI access", async ({ page }) => {
  const exam = gate();
  await mockLearning(page, { exam: exam.promise });
  try {
    await page.goto("/learning");
    await expect(page.getByRole("heading", { name: "บทเรียน 1", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "ส่งคำถาม", exact: true })).toHaveCount(0);
  } finally { exam.release(); }
  await expect(page.getByLabel("คำถามเกี่ยวกับบทเรียน")).toBeVisible();
});

test("rapid lesson changes ignore stale responses and preserve the unsent AI draft", async ({ page }) => {
  const second = gate();
  await mockLearning(page, { secondLesson: second.promise });
  await page.goto("/learning");
  const input = page.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill("อย่าล้างร่างเมื่อเปลี่ยนบทเรียน");
  try {
    const request = page.waitForRequest(`**/lessons/${lessons[1]}`);
    await page.getByLabel("บทเรียนในฐานข้อมูล").selectOption(lessons[1]);
    await request;
    await page.getByLabel("บทเรียนในฐานข้อมูล").selectOption(lessons[2]);
    await expect(page.getByRole("heading", { name: "บทเรียน 3", exact: true })).toBeVisible();
    await expect(input).toHaveValue("อย่าล้างร่างเมื่อเปลี่ยนบทเรียน");
    const response = page.waitForResponse(`**/lessons/${lessons[1]}`);
    second.release();
    await response;
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.getByRole("heading", { name: "บทเรียน 3", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "บทเรียน 2", exact: true })).toHaveCount(0);
  } finally { second.release(); }
});

test("changing accounts discards the previous account's AI draft", async ({ page }) => {
  const calls = await mockLearning(page);
  await page.goto("/learning");
  const input = page.getByLabel("คำถามเกี่ยวกับบทเรียน");
  await input.fill("ร่างส่วนตัวของบัญชีเดิม");
  calls.user = "15000000-0000-4000-8000-000000000099";
  const before = calls.session;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(() => calls.session).toBeGreaterThan(before);
  await expect(page.getByRole("link", { name: `Learner ${calls.session}`, exact: true })).toBeVisible();
  await expect(input).toHaveValue("");
});
