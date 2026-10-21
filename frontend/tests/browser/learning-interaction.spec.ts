import { expect, test } from "@playwright/test";

test("lesson explanation opens only after learner selects the example field", async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({
    json: { data: { csrf_token: "test-only", expires_at: "2099-01-01T00:00:00Z", user: {
      id: "00000000-0000-4000-8000-000000000099", display_name: "Test Analyst", email: "analyst@example.test", role: "analyst", status: "active",
    } } },
  }));
  await page.route("**/api/v1/lessons/*", (route) => route.fulfill({ json: { data: {
    id: "15000000-0000-4000-8000-000000000101", level_id: "15000000-0000-4000-8000-000000000001", version: 1, title: "อ่าน HTTP request และผลตอบกลับ",
    steps: [{ id: "method_path", title: "Method และ Path", target: "GET /api/profile", explanation: "GET ขออ่าน resource", limitation: "ยังไม่ทราบผู้ใช้" }],
  } } }));
  await page.route("**/api/v1/me/learning-path", (route) => route.fulfill({ json: { data: { lessons: [], next_action: "complete_lesson" } } }));
  await page.route("**/api/v1/exam/attempts/active", (route) => route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } }));
  await page.route("**/api/v1/exam/attempts/latest/result", (route) => route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } }));

  await page.goto("/learning");
  const save = page.getByRole("button", { name: "เข้าใจแล้ว บันทึกขั้นนี้" });
  await expect(save).toBeDisabled();
  await expect(page.getByText("ยังไม่ทราบผู้ใช้")).toHaveCount(0);
  await page.getByRole("button", { name: /กดดู: Method และ Path/ }).click();
  await expect(page.getByText("ยังไม่ทราบผู้ใช้")).toBeVisible();
  await expect(save).toBeEnabled();
});
