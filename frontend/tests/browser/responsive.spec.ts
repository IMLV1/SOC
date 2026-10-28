import { expect, test } from "@playwright/test";

for (const width of [320, 375, 768, 1024, 1440]) {
  test(`account layout and navigation remain usable at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    // This suite exercises layout/navigation, including auth-only destinations;
    // every API request stays inside deterministic fixtures.
    await page.route("**/api/**", (route) => route.abort());
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({
        json: {
          data: {
            csrf_token: "synthetic-responsive-csrf",
            expires_at: new Date(Date.now() + 3600000).toISOString(),
            user: {
              id: "11111111-1111-4111-8111-111111111111",
              display_name: "Analyst สำหรับทดสอบชื่อยาวบนหน้าจอมือถือ",
              email:
                "long-account-address-for-responsive-layout-verification@example.test",
              role: "analyst",
              status: "active",
            },
          },
        },
      }),
    );
    await page.route("**/api/v1/auth/google/status", (route) =>
      route.fulfill({ json: { data: { available: true, linked: false } } }),
    );
    await page.goto("/account");
    await expect(
      page.getByRole("heading", { name: "ข้อมูลบัญชี" }),
    ).toBeVisible();
    const menu = page.getByRole("button", { name: "เมนู", exact: true });
    if (width <= 760) {
      await expect(menu).toHaveAttribute("aria-expanded", "false");
      await expect(
        page.getByRole("link", { name: "สถานการณ์ฝึก", exact: true }),
      ).toBeHidden();
      await menu.click();
      await expect(
        page.getByRole("button", { name: "ปิดเมนู", exact: true }),
      ).toHaveAttribute("aria-expanded", "true");
      for (const link of await page.locator("nav a").all()) {
        const box = await link.boundingBox();
        expect(box?.height).toBeGreaterThanOrEqual(44);
      }
      await page
        .getByRole("link", {
          name: "Analyst สำหรับทดสอบชื่อยาวบนหน้าจอมือถือ",
          exact: true,
        })
        .click();
      await expect(menu).toHaveAttribute("aria-expanded", "false");
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const runs = page.getByRole("link", {
      name: "เปิดรอบฝึก (แยกจากข้อสอบ)",
      exact: true,
    });
    const demo = page.getByRole("link", { name: "ดูตัวอย่างก่อน", exact: true });
    await expect(runs).toHaveAttribute("href", "/runs");
    await expect(demo).toHaveAttribute("href", "/demo");
    for (const locator of [
      runs,
      demo,
      page.getByRole("button", { name: "เชื่อมบัญชี Google", exact: true }),
    ]) {
      const box = await locator.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.width).toBeGreaterThan(44);
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    }
    if (width <= 900)
      expect(
        await page
          .getByLabel("ยืนยันรหัสผ่าน SOC")
          .evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
      ).toBeGreaterThanOrEqual(16);
    await page.screenshot({
      path: testInfo.outputPath(`account-${width}.png`),
      fullPage: true,
    });
    for (const path of ["/", "/login", "/register"]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    if (width <= 760) {
      await page.getByRole("button", { name: "เมนู", exact: true }).focus();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("link", { name: "สถานการณ์ฝึก", exact: true }),
      ).toBeVisible();
      await page
        .getByRole("link", { name: "สถานการณ์ฝึก", exact: true })
        .click();
      await expect(page).toHaveURL(/\/scenarios$/);
      await expect(
        page.getByRole("button", { name: "เมนู", exact: true }),
      ).toHaveAttribute("aria-expanded", "false");
    }
  });
}
