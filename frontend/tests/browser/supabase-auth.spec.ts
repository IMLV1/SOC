import { expect, test } from "@playwright/test";

for (const linked of [true, false]) {
  test(`account Google status is verified, not taken from success query (${linked})`, async ({ page }) => {
    await page.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/auth/session")
        return route.fulfill({ json: { data: {
          csrf_token: "offline", expires_at: "2099-01-01T00:00:00Z",
          user: { id: "11111111-1111-4111-8111-111111111111", display_name: "Learner",
            email: "learner@example.test", role: "analyst", status: "active" },
        } } });
      if (path === "/api/v1/auth/google/status")
        return route.fulfill({ json: { data: { available: true, linked, link_available: false,
          provider_origin: "https://abcdefghijklmnopqrst.supabase.co" } } });
      return route.abort();
    });
    await page.goto("/account?google=success");
    const message = linked ? "เชื่อมบัญชี Google แล้ว ใช้ Google เข้าบัญชีเดิมได้" : "บัญชีนี้ยังไม่ได้เชื่อม Google";
    await expect(page.getByText(message, { exact: true })).toBeVisible();
    await expect(page.getByText("เชื่อมต่อ Google สำเร็จ", { exact: true })).toHaveCount(0);
    await expect(page.getByText(/การรวมบัญชีเดิมต้องให้ผู้ดูแล/)).toHaveCount(0);
    await expect(page.getByLabel("ยืนยันรหัสผ่าน SOC")).toHaveCount(0);
    await page.reload();
    await expect(page.getByText(message, { exact: true })).toBeVisible();
  });
}

test("Supabase email confirmation stays on registration without claiming login", async ({ page }) => {
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/csrf")
      return route.fulfill({ json: { data: { csrf_token: "offline" } } });
    if (path === "/api/v1/auth/register")
      return route.fulfill({ status: 202, json: { data: { status: "email_confirmation_required" } } });
    if (path === "/api/v1/auth/google/status")
      return route.fulfill({ json: { data: { available: false, linked: false } } });
    return route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } });
  });
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Learner");
  await page.getByLabel("อีเมล", { exact: true }).fill("learner@example.test");
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("Test123!9");
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(page.getByText(/กรุณายืนยันอีเมลจากข้อความของ Supabase/)).toBeVisible();
  await expect(page).toHaveURL(/\/register$/);
});

test("Google login accepts only the configured Supabase authorization origin", async ({ page }) => {
  const origin = "https://abcdefghijklmnopqrst.supabase.co";
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/google/status")
      return route.fulfill({ json: { data: { available: true, linked: false, link_available: false, provider_origin: origin } } });
    if (path === "/api/v1/auth/csrf")
      return route.fulfill({ json: { data: { csrf_token: "offline" } } });
    if (path === "/api/v1/auth/google/start")
      return route.fulfill({ json: { data: { authorization_url: origin + "/auth/v1/authorize?provider=google" } } });
    return route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } });
  });
  await page.route(origin + "/**", (route) => route.fulfill({ contentType: "text/html", body: "<h1>Offline Supabase Auth</h1>" }));
  await page.goto("/login");
  await page.getByRole("button", { name: "เข้าสู่ระบบด้วย Google" }).click();
  await expect(page.getByRole("heading", { name: "Offline Supabase Auth" })).toBeVisible();
});
