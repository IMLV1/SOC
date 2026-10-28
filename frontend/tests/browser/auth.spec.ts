import { expect, test } from "@playwright/test";

test("new registration asks for 6–12 characters while login still accepts old longer passwords", async ({ page }) => {
  await page.route("**/api/**", (route) => {
    if (new URL(route.request().url()).pathname === "/api/v1/auth/google/status") {
      return route.fulfill({ json: { data: { available: false, linked: false } } });
    }
    return route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } });
  });
  await page.goto("/register");
  const newPassword = page.getByLabel("รหัสผ่าน", { exact: true });
  await expect(newPassword).toHaveAttribute("minlength", "6");
  await expect(newPassword).toHaveAttribute("maxlength", "12");
  await expect(page.getByText("รหัสผ่านสำหรับบัญชีใหม่ 6–12 ตัวอักษร")).toBeVisible();
  await page.goto("/login");
  const oldPassword = page.getByLabel("รหัสผ่าน", { exact: true });
  await expect(oldPassword).toHaveAttribute("minlength", "5");
  await expect(oldPassword).toHaveAttribute("maxlength", "128");
});

test("register signs in immediately; refresh, logout and later login use the same-origin API", async ({
  page,
  browser,
}) => {
  const email = `browser-${Date.now()}@example.test`;
  const password = crypto.randomUUID().slice(0, 6);
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Browser Analyst");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(page).toHaveURL(/\/account$/);
  expect((await page.request.get("/api/v1/me")).status()).toBe(200);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "เริ่มบทเรียนพื้นฐาน" })).toHaveAttribute("href", "/learning");
  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const cookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === "soc_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "soc_session",
  );
  const quota = await (await page.request.get("/api/v1/me/quota")).json();
  expect(quota.data.daily_runs).toBe(10);
  expect(quota.data.daily_ai_requests).toBe(20);
  const invalidLogout = await page.request.post("/api/v1/auth/logout", {
    data: {},
    headers: { Origin: new URL(page.url()).origin },
  });
  expect(invalidLogout.status()).toBe(403);
  const guest = await browser.newContext({
    baseURL: new URL(page.url()).origin,
  });
  expect(
    (
      await guest.request.get(
        `/api/v1/me?user_id=${quota.data.id ?? "ignored"}`,
      )
    ).status(),
  ).toBe(401);
  await guest.close();
  // A session response already in flight must not restore the UI after logout.
  let release!: () => void;
  let fetched!: () => void;
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  const received = new Promise<void>((resolve) => {
    fetched = resolve;
  });
  await page.route("**/api/v1/auth/session", async (route) => {
    const response = await route.fetch();
    fetched();
    await delayed;
    await route.fulfill({ response });
  });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await received;
  await page.getByRole("button", { name: "ออกจากระบบ" }).click();
  await expect(
    page.getByRole("heading", { name: "กรุณาเข้าสู่ระบบ" }),
  ).toBeVisible();
  const staleResponse = page.waitForResponse("**/api/v1/auth/session");
  release();
  await (await staleResponse).finished();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
  );
  await expect(page.getByText(email, { exact: true })).toHaveCount(0);
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
  await page.unroute("**/api/v1/auth/session");
  await page.goto("/login");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
});

test("Guest demo is readable, cannot mutate and fits mobile/tablet/desktop", async ({
  page,
}) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/demo");
    await expect(
      page.getByRole("heading", { name: "GET /help", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: /กด Method/ })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  expect(
    (await page.request.post("/api/v1/demo/events", { data: {} })).status(),
  ).toBe(405);
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
});

test("Guest can practice reading each request field without signing in", async ({ page }) => {
  await page.goto("/demo");
  const next = page.getByRole("button", { name: "ไปขั้นถัดไป" });
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: "Path /help" }).click();
  await expect(page.getByRole("status").getByText("ยังไม่ใช่ช่องนี้")).toBeVisible();
  await page.getByRole("button", { name: "Method GET" }).click();
  await expect(page.getByText(/GET มักใช้ขออ่านข้อมูล/)).toBeVisible();
  await next.click();
  await page.getByRole("button", { name: "Path /help" }).click();
  await next.click();
  await page.getByRole("button", { name: "Response status 200" }).click();
  await expect(page.getByText(/ไม่ได้แปลว่ามีการบุกรุก/)).toBeVisible();
  await next.click();
  await page.getByRole("button", { name: /Time \(UTC\)/ }).click();
  await next.click();
  await expect(page.getByRole("heading", { name: "ลองเชื่อมข้อมูลหลายจุด" })).toBeVisible();
  await page.getByRole("button", { name: "ลองตัวอย่างถัดไป" }).click();
  await expect(page.getByRole("heading", { name: "GET /missing-page" })).toBeVisible();
  await page.getByRole("button", { name: "Method GET" }).click();
  await next.click();
  await page.getByRole("button", { name: "Path /missing-page" }).click();
  await next.click();
  await page.getByRole("button", { name: "Response status 404" }).click();
  await expect(page.getByText(/ไม่ได้พิสูจน์ว่าทั้งเคสปลอดภัย/)).toBeVisible();
});
