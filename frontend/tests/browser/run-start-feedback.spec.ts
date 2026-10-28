import { expect, test, type Page } from "@playwright/test";

async function mockTraining(page: Page, status: number, code: string, emptyCatalog = false) {
  let listLoads = 0;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/session") return route.fulfill({ json: { data: {
      csrf_token: "test-only", expires_at: "2099-01-01T00:00:00Z", user: {
        id: "00000000-0000-4000-8000-000000000099", display_name: "Test Analyst", email: "analyst@example.test", role: "analyst", status: "active",
      },
    } } });
    if (path === "/api/v1/auth/csrf") return route.fulfill({ json: { data: { csrf_token: "test-only" } } });
    if (path === "/api/v1/scenarios") return route.fulfill({ json: { data: emptyCatalog ? [] : [{ id: "00000000-0000-4000-8000-000000000002", title: "S02 training example", duration_ms: 75000, version: 1, difficulty: "beginner", learning_objectives: ["Read evidence"] }] } });
    if (path === "/api/v1/runs" && request.method() === "GET") {
      listLoads += 1;
      return route.fulfill({ json: { data: [], meta: { request_id: "test-only", next_cursor: null } } });
    }
    if (path === "/api/v1/runs" && request.method() === "POST") return route.fulfill({ status, json: status === 201 ? { data: { id: "00000000-0000-4000-8000-000000000005" } } : { error: { code } } });
    return route.abort();
  });
  return () => listLoads;
}

test("start failure stays visible after automatic run-list refresh", async ({ page }) => {
  const listLoads = await mockTraining(page, 409, "RUN_ALREADY_RUNNING");
  await page.goto("/runs");
  await page.getByRole("button", { name: "เริ่มรอบฝึก", exact: true }).click();
  await expect.poll(listLoads).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("มีรอบฝึกหรือข้อสอบที่กำลังทำอยู่");
  await expect(page.getByRole("link", { name: "ตรวจสถานะข้อสอบ", exact: true })).toHaveAttribute("href", "/learning");
});

test("quota failure is not erased by refreshing the run list", async ({ page }) => {
  const listLoads = await mockTraining(page, 429, "RUN_QUOTA_EXCEEDED");
  await page.goto("/runs");
  await page.getByRole("button", { name: "เริ่มรอบฝึก", exact: true }).click();
  await expect.poll(listLoads).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("main").getByRole("alert")).toContainText("โควตารอบฝึกวันนี้หมดแล้ว");
});

for (const failure of [
  { status: 401, code: "UNAUTHENTICATED", message: "เซสชันหมดอายุ" },
  { status: 503, code: "UNAVAILABLE", message: "ระบบเริ่มรอบฝึกยังไม่พร้อม" },
  { status: 409, code: "IDEMPOTENCY_CONFLICT", message: "คำขอซ้ำไม่ตรงกับคำขอเดิม" },
]) {
  test(`start failure ${failure.code} shows an actionable reason after refresh`, async ({ page }) => {
    const listLoads = await mockTraining(page, failure.status, failure.code);
    await page.goto("/runs");
    await page.getByRole("button", { name: "เริ่มรอบฝึก", exact: true }).click();
    await expect.poll(listLoads).toBeGreaterThanOrEqual(2);
    await expect(page.getByRole("main").getByRole("alert")).toContainText(failure.message);
  });
}

test("empty runner catalog explains disabled start and links to database practice", async ({ page }) => {
  await mockTraining(page, 503, "UNAVAILABLE", true);
  await page.goto("/runs");
  await expect(page.getByRole("button", { name: "ยังไม่มีสถานการณ์ให้เริ่ม", exact: true })).toBeDisabled();
  await expect(page.getByRole("link", { name: "ฝึกอ่านหลักฐานรวมพร้อมบันทึกคำตอบ", exact: true })).toHaveAttribute("href", "/practice");
});

test("successful start still navigates to the run returned by the mocked API", async ({ page }) => {
  await mockTraining(page, 201, "");
  await page.goto("/runs");
  await page.getByRole("button", { name: "เริ่มรอบฝึก", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\/00000000-0000-4000-8000-000000000005$/);
});
