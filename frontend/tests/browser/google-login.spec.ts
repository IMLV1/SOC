import { expect, test } from "@playwright/test";

test("Google availability and callback messages are truthful on responsive login", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/google/status", (route) =>
    route.fulfill({ json: { data: { available: false, linked: false } } }),
  );
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/login?google=link_required");
    await expect(
      page.getByText("Google login ยังไม่เปิดใช้งานใน environment นี้"),
    ).toBeVisible();
    await expect(page.getByText(/มีบัญชี SOC อีเมลนี้แล้ว/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "เข้าสู่ระบบด้วย Google" }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});

test("Google login uses CSRF POST before navigating to the fixed Google destination", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/google/status", (route) =>
    route.fulfill({ json: { data: { available: true, linked: false } } }),
  );
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ json: { data: { csrf_token: "offline-browser-csrf" } } }),
  );
  let posted = false;
  await page.route("**/api/v1/auth/google/start", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBe(
      "offline-browser-csrf",
    );
    expect(route.request().postDataJSON()).toEqual({ purpose: "login" });
    posted = true;
    await route.fulfill({
      json: {
        data: {
          authorization_url:
            "https://accounts.google.com/o/oauth2/v2/auth?state=browser-test",
        },
      },
    });
  });
  await page.route("https://accounts.google.com/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<h1>Offline Google destination</h1>",
    }),
  );
  await page.goto("/login");
  const logo = page
    .getByRole("button", { name: "เข้าสู่ระบบด้วย Google" })
    .locator("svg.google-logo");
  await expect(logo).toBeVisible();
  await expect(logo).toHaveAttribute("width", "24");
  await expect(logo).toHaveAttribute("height", "24");
  await expect(logo).toHaveAttribute("aria-hidden", "true");
  await page.getByRole("button", { name: "เข้าสู่ระบบด้วย Google" }).click();
  await expect(
    page.getByRole("heading", { name: "Offline Google destination" }),
  ).toBeVisible();
  expect(posted).toBe(true);
});

test("link form preserves password draft on failed reauthentication and shows linked status", async ({
  page,
}) => {
  let linked = false;
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      json: {
        data: {
          csrf_token: "offline",
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          user: {
            id: "11111111-1111-4111-8111-111111111111",
            display_name: "Analyst",
            email: "test@example.test",
            role: "analyst",
            status: "active",
          },
        },
      },
    }),
  );
  await page.route("**/api/v1/auth/google/status", (route) =>
    route.fulfill({ json: { data: { available: true, linked } } }),
  );
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ json: { data: { csrf_token: "offline" } } }),
  );
  await page.route("**/api/v1/auth/google/start", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      purpose: "link",
      password: "Synthetic-password-123",
    });
    await route.fulfill({
      status: 401,
      json: { error: { code: "REAUTH_REQUIRED" } },
    });
  });
  await page.goto("/account");
  await page.getByLabel("ยืนยันรหัสผ่าน SOC").fill("Synthetic-password-123");
  await page
    .getByRole("button", { name: "เชื่อมบัญชี Google", exact: true })
    .click();
  await expect(
    page.getByText("กรุณาตรวจรหัสผ่านหรือเข้าสู่ระบบใหม่"),
  ).toBeVisible();
  await expect(page.getByLabel("ยืนยันรหัสผ่าน SOC")).toHaveValue(
    "Synthetic-password-123",
  );
  linked = true;
  await page.reload();
  await expect(
    page.getByText("เชื่อมบัญชี Google แล้ว ใช้ Google เข้าบัญชีเดิมได้"),
  ).toBeVisible();
  await expect(page.getByLabel("ยืนยันรหัสผ่าน SOC")).toHaveCount(0);
});

test("older preview API shows Google unavailable without a misleading retry message", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/google/status", (route) =>
    route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND" } } }),
  );
  await page.goto("/login");
  await expect(
    page.getByText("Google login ยังไม่เปิดใช้งานใน environment นี้"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "เข้าสู่ระบบด้วย Google" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("ตรวจสถานะ Google ไม่สำเร็จ กรุณาโหลดหน้าใหม่"),
  ).toHaveCount(0);
});
