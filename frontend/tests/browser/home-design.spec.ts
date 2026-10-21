import { expect, test } from "@playwright/test";

for (const width of [375, 768, 1440]) {
  test(`landing hierarchy stays usable at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } }),
    );
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "เห็นหลักฐาน คิดเป็นระบบ" })).toBeVisible();

    const start = page.getByRole("link", { name: "ลองอ่าน request ตัวอย่าง" }).first();
    const box = await start.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThan(900);
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.fonts.check('16px "Anakotmai"', "เรียนรู้"))).toBe(true);
    expect(await page.evaluate(() => document.fonts.check('16px "JetBrains Mono"', "SOC"))).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`home-${width}.png`), fullPage: true });
  });
}
