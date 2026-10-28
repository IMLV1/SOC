import { execFileSync } from "node:child_process";
import { expect, test, type Browser } from "@playwright/test";

async function reviewWithAssignedInstructor(browser: Browser, learnerPage: import("@playwright/test").Page, analystId: string) {
  const instructorId = process.env.SOC_TEST_INSTRUCTOR_ID;
  const instructorPassword = process.env.SOC_TEST_INSTRUCTOR_PASSWORD;
  if (!instructorId || !instructorPassword) return false;

  execFileSync(
    process.env.SOC_DOCKER_BIN ?? "docker",
    ["compose", "run", "--rm", "-T", "--no-deps", "seed", "python", "-m", "app.db.provision", "assign", "--instructor", instructorId, "--analyst", analystId],
    { cwd: process.env.SOC_REPO_ROOT ?? process.cwd(), env: process.env, stdio: "pipe" },
  );

  const instructorContext = await browser.newContext({
    baseURL: process.env.SOC_SMOKE_ORIGIN ?? "http://127.0.0.1:3000",
  });
  const instructorPage = await instructorContext.newPage();
  try {
    await instructorPage.goto("/login");
    await instructorPage.getByLabel("อีเมล", { exact: true }).fill(process.env.SOC_TEST_INSTRUCTOR_EMAIL ?? "");
    await instructorPage.getByLabel("รหัสผ่าน", { exact: true }).fill(instructorPassword);
    await instructorPage.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
    await expect(instructorPage).toHaveURL(/\/account$/);
    await instructorPage.goto("/instructor/exams");
    await instructorPage.getByRole("link", { name: /Learning Analyst · needs_review/ }).click();
    await expect(instructorPage.getByRole("heading", { name: "ตรวจคำตอบข้อสอบ" })).toBeVisible();
    await instructorPage.getByLabel("analysis").selectOption("0");
    await instructorPage.getByLabel("reasoning").selectOption("0");
    await instructorPage.getByLabel("เหตุผลการตรวจ").fill("ตรวจหลักฐานจาก event ที่ส่งจริงแล้ว ต้องทบทวนการวิเคราะห์ก่อนสอบใหม่");
    await instructorPage.getByRole("button", { name: "บันทึกผลตรวจ" }).click();
    await expect(instructorPage.getByRole("heading", { name: "ผล: failed" })).toBeVisible();
  } finally {
    await instructorContext.close();
  }

  await learnerPage.reload();
  await expect(learnerPage.getByText("ผลข้อสอบ: failed")).toBeVisible();
  await expect(learnerPage.getByText("ควรทบทวนแนวทางของเกณฑ์นี้").first()).toBeVisible();
  return true;
}

function expireFailedAttemptCooldown(attemptId: string) {
  if (!/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(attemptId)) {
    throw new Error("Expected a UUID for the failed exam attempt.");
  }
  if (!process.env.COMPOSE_PROJECT_NAME?.startsWith("soc-ci-")) {
    throw new Error("Cooldown expiry is allowed only in a disposable soc-ci-* Compose project.");
  }

  const databaseScript = [
    "import asyncio, sys",
    "from uuid import UUID",
    "from sqlalchemy import text",
    "from app.db.config import database_url",
    "from app.db.session import Database",
    "async def main():",
    "    database = Database(database_url('migration_owner'))",
    "    try:",
    "        async with database.sessions() as session, session.begin():",
    "            expired = await session.scalar(text(\"\"\"UPDATE app.exam_attempts",
    "                SET started_at=clock_timestamp()-interval '2 hours',",
    "                    finalized_at=clock_timestamp()-interval '2 hours'",
    "                WHERE id=:attempt AND status='failed'",
    "                  AND started_at>clock_timestamp()-interval '24 hours'",
    "                RETURNING id\"\"\"), {'attempt': UUID(sys.argv[1])})",
    "            if expired is None:",
    "                raise RuntimeError('Failed attempt was not found in the disposable database.')",
    "    finally:",
    "        await database.close()",
    "asyncio.run(main())",
  ].join("\n");

  execFileSync(
    process.env.SOC_DOCKER_BIN ?? "docker",
    ["compose", "run", "--rm", "-T", "--no-deps", "seed", "python", "-c", databaseScript, attemptId],
    { cwd: process.env.SOC_REPO_ROOT ?? process.cwd(), env: process.env, stdio: "pipe" },
  );
}

test("lesson progress is saved on the server, resumes after refresh, and stays usable on mobile/tablet/desktop", async ({
  page,
  browser,
}) => {
  const email = `learning-${Date.now()}@example.test`;
  const password = crypto.randomUUID().slice(0, 10);

  await page.goto("/learning");
  await expect(
    page.getByRole("heading", { name: "เข้าสู่ระบบเพื่ออ่านบทเรียน" }),
  ).toBeVisible();
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Learning Analyst");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();

  await page.goto("/learning");
  await expect(page.getByText("ขั้น 1 / 5")).toBeVisible();
  await expect(page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้" })).toBeDisabled();
  await page.getByRole("button", { name: /กดดู: Method และ Path/ }).click();
  await expect(page.getByText(/คำขอหนึ่งรายการยังไม่บอกว่าใคร/)).toBeVisible();
  await page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้" }).click();
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
    await page.getByRole("button", { name: /กดดู:/ }).click();
    await page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้" }).click();
  }
  await expect(page.getByText("ครบทุกขั้นแล้ว")).toBeVisible();
  await page.getByRole("button", { name: "จบบทเรียนและบันทึก" }).click();
  await expect(page.getByText("จบบทเรียนแล้ว")).toBeVisible();
  await expect(page.getByRole("button", { name: "เริ่มข้อสอบระดับนี้" })).toBeVisible();

  // The level now contains three DB-backed lessons, not one static starter.
  const catalogResponse = await page.request.get("/api/v1/learning-path");
  expect(catalogResponse.ok()).toBe(true);
  const catalog = (await catalogResponse.json()).data;
  for (const lesson of catalog.levels[0].lessons.slice(1)) {
    await page.getByRole("combobox", { name: "บทเรียนในฐานข้อมูล", exact: true }).selectOption(lesson.id);
    for (let step = 1; step <= 5; step += 1) {
      await expect(page.getByText(`ขั้น ${step} / 5`)).toBeVisible();
      await page.getByRole("button", { name: /กดดู:/ }).click();
      await page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้" }).click();
    }
    await page.getByRole("button", { name: "จบบทเรียนและบันทึก" }).click();
    await expect(page.getByText("จบบทเรียนแล้ว")).toBeVisible();
  }

  await page.getByRole("button", { name: "เริ่มข้อสอบระดับนี้" }).click();
  await expect(page.getByRole("heading", { name: "Investigation case" })).toBeVisible();
  await page.getByRole("checkbox").first().check();
  await page.getByLabel("เหตุผลและการวิเคราะห์").fill(
    "The request and response events provide the evidence for this assessment.",
  );
  await page.getByRole("button", { name: "ส่งข้อสอบ" }).click();
  await expect(page.getByText("ผลข้อสอบ: needs_review")).toBeVisible();
  await expect(page.getByText("ส่งคำตอบแล้ว รอ Instructor ตรวจ ไม่มีการประเมินผ่านอัตโนมัติ")).toBeVisible();

  const sessionResponse = await page.request.get("/api/v1/auth/session");
  const analystId = (await sessionResponse.json()).data.user.id as string;
  const reviewedAgainstLiveApi = await reviewWithAssignedInstructor(browser, page, analystId);
  if (!reviewedAgainstLiveApi) {
    // Non-Compose development runs model the later Instructor decision; the
    // disposable CI Compose harness provisions and assigns a real Instructor.
    await page.route("**/api/v1/exam/attempts/active", (route) =>
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: { code: "NOT_FOUND" } }) }),
    );
    await page.route("**/api/v1/exam/attempts/latest/result", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: { attempt_id: "16000000-0000-4000-8000-000000000001", status: "failed", score: 4, maximum: 10, criteria: [] } }) }),
    );
    await page.route("**/api/v1/learning/levels/*/attempts", (route) =>
      route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ error: { code: "EXAM_COOLDOWN_ACTIVE", message: "Retake cooldown is active" } }) }),
    );
  }

  // An immediate retry must respect the server-enforced one-hour cooldown.
  if (!reviewedAgainstLiveApi) {
    await page.reload();
    await expect(page.getByText("ผลข้อสอบ: failed")).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "เริ่ม attempt ถัดไป" })).toBeVisible();
  await page.getByRole("button", { name: "เริ่ม attempt ถัดไป" }).click();
  await expect(page.locator("p[role='alert']")).toContainText("หลังสอบตก ต้องรอ 1 ชั่วโมง");
  await expect(page.getByText("ผลข้อสอบ: failed")).toBeVisible();
  await expect(page.getByRole("button", { name: "เริ่ม attempt ถัดไป" })).toBeVisible();

  const path = await (await page.request.get("/api/v1/me/learning-path")).json();
  expect(path.data.lessons).toHaveLength(3);
  for (const progress of path.data.lessons) {
    expect(progress.completed_steps).toHaveLength(5);
    expect(progress.completed_at).not.toBeNull();
  }
  expect(path.data.next_action).toBe("review_lesson_exam_unavailable");

  if (reviewedAgainstLiveApi && process.env.COMPOSE_PROJECT_NAME?.startsWith("soc-ci-")) {
    const failedResponse = await page.request.get("/api/v1/exam/attempts/latest/result");
    expect(failedResponse.ok()).toBe(true);
    const failedAttempt = (await failedResponse.json()).data;
    expect(failedAttempt.status).toBe("failed");
    expireFailedAttemptCooldown(failedAttempt.attempt_id);

    await page.getByRole("button", { name: "เริ่ม attempt ถัดไป" }).click();
    await expect(page.getByRole("heading", { name: "Investigation case" })).toBeVisible();

    const activeResponse = await page.request.get("/api/v1/exam/attempts/active");
    expect(activeResponse.ok()).toBe(true);
    const retake = (await activeResponse.json()).data;
    expect(retake.status).toBe("in_progress");
    expect(retake.id).not.toBe(failedAttempt.attempt_id);
  }
});
