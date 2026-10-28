import { expect, test, type Page } from "@playwright/test";

const session = {
  csrf_token: "offline-session",
  expires_at: "2099-01-01T00:00:00Z",
  user: {
    id: "11111111-1111-4111-8111-111111111111",
    display_name: "Test Learner",
    email: "learner@example.test",
    role: "analyst",
    status: "active",
  },
};

async function mockOtherApi(page: Page) {
  await page.route("**/api/**", (route) => {
    if (new URL(route.request().url()).pathname === "/api/v1/auth/google/status")
      return route.fulfill({ json: { data: { available: false, linked: false } } });
    return route.abort();
  });
}

for (const path of ["/login", "/register"]) {
  test(`active session redirects ${path} to account, including refresh`, async ({ page }) => {
    await mockOtherApi(page);
    await page.route("**/api/v1/auth/session", (route) => route.fulfill({ json: { data: session } }));
    await page.goto(path);
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: "บัญชีของคุณ" })).toBeVisible();
    await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toHaveCount(0);
  });

  test(`401 allows guest form at ${path}`, async ({ page }) => {
    await mockOtherApi(page);
    await page.route("**/api/v1/auth/session", (route) => route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } }));
    await page.goto(path);
    await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(path + "$"));
  });

  test(`pending session never flashes a form at ${path}`, async ({ page }) => {
    await mockOtherApi(page);
    let release!: () => void;
    const ready = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/api/v1/auth/session", async (route) => {
      await ready;
      await route.fulfill({ json: { data: session } });
    });
    await page.goto(path);
    await expect(page.getByRole("main")).toContainText("กำลังตรวจสอบการเข้าสู่ระบบ");
    await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toHaveCount(0);
    release();
    await expect(page).toHaveURL(/\/account$/);
  });
}

test("session outage is not treated as logged out, retry can confirm a guest", async ({ page }) => {
  await mockOtherApi(page);
  let unavailable = true;
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({
    status: unavailable ? 503 : 401,
    json: { error: { code: unavailable ? "UNAVAILABLE" : "AUTH_REQUIRED" } },
  }));
  await page.goto("/login");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("ยังยืนยันสถานะการเข้าสู่ระบบไม่ได้");
  await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toHaveCount(0);
  unavailable = false;
  await page.getByRole("button", { name: "ตรวจสอบอีกครั้ง", exact: true }).click();
  await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toBeVisible();
});

test("logout allows returning to the login form", async ({ page }) => {
  await mockOtherApi(page);
  let active = true;
  await page.route("**/api/v1/auth/session", (route) => route.fulfill(active
    ? { json: { data: session } }
    : { status: 401, json: { error: { code: "AUTH_REQUIRED" } } }));
  await page.route("**/api/v1/auth/logout", (route) => {
    active = false;
    return route.fulfill({ status: 204 });
  });
  await page.goto("/login");
  await expect(page).toHaveURL(/\/account$/);
  await page.getByRole("button", { name: "ออกจากระบบ", exact: true }).click();
  await expect(page.getByRole("heading", { name: "กรุณาเข้าสู่ระบบ" })).toBeVisible();
  await page.getByRole("main").getByRole("link", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page.getByLabel("รหัสผ่าน", { exact: true })).toBeVisible();
});
