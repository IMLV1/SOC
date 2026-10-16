import { expect, test } from "@playwright/test";

test("register does not log in; cookie login, refresh and logout use the same-origin API", async ({
  page,
  browser,
}) => {
  const email = `browser-${Date.now()}@example.test`;
  const password = `Test-only-${Date.now()}-password`;
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Browser Analyst");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(
    page.getByText("สมัครสำเร็จ กรุณาเข้าสู่ระบบด้วยบัญชีของคุณ"),
  ).toBeVisible();
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
  await page.getByRole("link", { name: "ไปเข้าสู่ระบบ" }).click();
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByText(email, { exact: true })).toBeVisible();
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
