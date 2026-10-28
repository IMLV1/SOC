import { expect, test } from "@playwright/test";

test.describe("Magic UI learning lab", () => {
  test("home page composes the aurora, spotlight card and safe learning path", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "เห็นหลักฐาน คิดเป็นระบบ" }),
    ).toBeVisible();
    await expect(page.getByText("ไม่สั่งการระบบจริง")).toBeVisible();
    await expect(page.locator(".hero-grid-pattern")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    await expect(page.locator(".learning-pillar")).toHaveCount(3);

    const card = page.locator(".workflow-visual");
    // A small hover near the corner verifies that the CSS variables are
    // viewport-independent percentages rather than raw pixel coordinates.
    const bounds = await card.boundingBox();
    expect(bounds).not.toBeNull();
    await card.hover({ position: { x: 24, y: 32 } });
    const spotlight = await card.evaluate((element) => ({
      x: Number.parseFloat(element.style.getPropertyValue("--magic-x")),
      y: Number.parseFloat(element.style.getPropertyValue("--magic-y")),
    }));
    expect(spotlight.x).toBeGreaterThan(0);
    expect(spotlight.x).toBeLessThan(12);
    expect(spotlight.y).toBeGreaterThan(0);
    expect(spotlight.y).toBeLessThan(18);
  });

  test("mobile learning layout has no horizontal overflow", async ({ page }) => {
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({ status: 401, json: { error: { code: "AUTH_REQUIRED" } } }),
    );
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const register = page.getByRole("link", {
      name: "สมัครเพื่อบันทึกความคืบหน้า",
      exact: true,
    });
    await expect(register).toBeVisible();
    await expect(register).toHaveAttribute("href", "/register");

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("decorative animation respects reduced-motion preference", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");

    const animationDuration = await page
      .locator(".aurora-text")
      .evaluate((element) => getComputedStyle(element).animationDuration);
    expect(animationDuration).toBe("1e-05s");
  });
});
