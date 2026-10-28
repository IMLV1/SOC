import { test, expect } from "@playwright/test";

test("Guest catalog shows public metadata without exam controls", async ({
  page,
}) => {
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/scenarios");
    await expect(
      page.getByRole("heading", { name: "สถานการณ์ฝึก" }),
    ).toBeVisible();
    await expect(
      page.getByText("รายการนี้ไม่ใช่ข้อสอบเลื่อนระดับ", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "ไปเส้นทางบทเรียนและข้อสอบ", exact: true }),
    ).toHaveAttribute("href", "/learning");
    await expect(page.locator("article")).toHaveCount(1);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  const response = await page.request.get("/api/v1/scenarios");
  expect(response.status()).toBe(200);
  expect(await response.text()).not.toMatch(
    /fixture|rubric|threat_label|SIM-T-204|records\/export/,
  );
  const scenarios = (await response.json()).data;
  expect(
    (
      await page.request.post("/api/v1/runs", {
        data: { scenario_ids: [scenarios[0].id], mode: "exam" },
      })
    ).status(),
  ).toBe(422);
  expect(
    (
      await page.request.post(
        "/api/v1/levels/00000000-0000-4000-8000-000000000005/attempts",
        { data: { scenario_ids: [scenarios[0].id], mode: "exam" } },
      )
    ).status(),
  ).toBe(404);
});

test("catalog loading, failure, retry and empty states", async ({ page }) => {
  let respond: (() => Promise<void>) | undefined;
  let mode = "loading";
  await page.route("**/api/v1/scenarios", async (route) => {
    if (mode === "loading") {
      await new Promise<void>((resolve) => {
        respond = async () => {
          await route.fulfill({ status: 503, json: {} });
          resolve();
        };
      });
    } else
      await route.fulfill({
        json: { data: [], meta: { request_id: "test", next_cursor: null } },
      });
  });
  await page.goto("/scenarios");
  await expect(page.getByText("กำลังโหลดสถานการณ์…")).toBeVisible();
  await expect.poll(() => Boolean(respond)).toBe(true);
  await respond!();
  await expect(page.getByText("โหลดสถานการณ์ไม่สำเร็จ")).toBeVisible();
  mode = "empty";
  await page.getByRole("button", { name: "ลองใหม่", exact: true }).click();
  await expect(page.getByText("ยังไม่มีสถานการณ์ที่เปิดให้ดู")).toBeVisible();
});
