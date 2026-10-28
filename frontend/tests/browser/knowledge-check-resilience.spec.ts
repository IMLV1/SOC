import { expect, test } from "@playwright/test";

test("failed written submit and reload preserve all ten pending answers", async ({ page }) => {
  const levelId = "15000000-0000-4000-8000-000000000001";
  const questions = Array.from({ length: 10 }, (_, index) => ({ id: `22000000-0000-4000-8000-${String(index + 10).padStart(12, "0")}`, ordinal: index + 1, version: 1, category: "written_knowledge", prompt: `อธิบายหลักฐานข้อ ${index + 1}` }));
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({ json: { data: { csrf_token: "test-only", user: { id: levelId, role: "analyst", display_name: "Learner", email: "learner@example.test", status: "active" }, expires_at: "2099-01-01T00:00:00Z" } } }));
  await page.route("**/api/v1/learning-path", (route) => route.fulfill({ json: { data: { levels: [{ id: levelId, ordinal: 1, title: "เริ่มต้น" }] } } }));
  await page.route(`**/api/v1/learning/levels/${levelId}/written-questions`, (route) => route.fulfill({ json: { data: questions } }));
  await page.route(`**/api/v1/learning/levels/${levelId}/written-submissions`, (route) => route.request().method() === "GET"
    ? route.fulfill({ json: { data: [] } })
    : route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE" } } }));
  await page.goto("/knowledge-check");
  const inputs = page.getByRole("textbox");
  await expect(inputs).toHaveCount(10);
  for (let index = 0; index < 10; index += 1) await inputs.nth(index).fill(`คำตอบที่ยังไม่ส่งข้อ ${index + 1}`);
  await page.getByRole("button", { name: "ส่งคำตอบครบ 10 ข้อ", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("คำตอบของคุณยังอยู่");
  await page.getByRole("button", { name: "โหลดใหม่", exact: true }).click();
  await expect(inputs).toHaveCount(10);
  for (let index = 0; index < 10; index += 1) await expect(inputs.nth(index)).toHaveValue(`คำตอบที่ยังไม่ส่งข้อ ${index + 1}`);
  await expect(page.getByRole("button", { name: "ส่งคำตอบครบ 10 ข้อ", exact: true })).toBeEnabled();
});
