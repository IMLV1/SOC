import { expect, test } from "@playwright/test";

test("auth-only preview disables runner controls and refuses direct queue writes", async ({ page }) => {
  test.skip(process.env.SOC_PREVIEW_MODE !== "auth_only", "Explicit preview acceptance only");
  const email = `preview-${Date.now()}@example.test`;
  const password = `Test-only-${Date.now()}-password`;
  await page.goto("/register");
  await expect(page.getByText(/Free preview: ทดสอบสมัครสมาชิก/)).toBeVisible();
  await page.getByLabel("ชื่อที่แสดง").fill("Preview Analyst");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await page.getByRole("link", { name: "ไปเข้าสู่ระบบ" }).click();
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  const cookie = (await page.context().cookies()).find(item => item.name === "soc_session");
  expect(cookie?.secure).toBe(true);
  expect(cookie?.httpOnly).toBe(true);
  await page.getByRole("link", { name: "รอบฝึกของฉัน" }).click();
  await expect(page.getByRole("button", { name: "Runner ยังไม่พร้อมบน preview" })).toBeDisabled();
  await expect(page.getByText("ยังไม่มีรอบฝึก", { exact: true })).toBeVisible();
  const csrf = await (await page.request.get("/api/v1/auth/csrf")).json();
  const refused = await page.request.post("/api/v1/runs", { data: { scenario_ids: [] },
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": csrf.data.csrf_token } });
  expect(refused.status()).toBe(503);
  expect((await refused.json()).error.code).toBe("PREVIEW_UNAVAILABLE");
  await page.screenshot({ path: "../test-results/render-preview-runs.png", fullPage: true });
  await page.getByRole("button", { name: "ออกจากระบบ" }).click();
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบ", exact: true })).toBeVisible();
});
