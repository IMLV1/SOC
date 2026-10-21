import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort());
});

test("JSON curriculum opens all nine lessons, reveals each explanation, and restores the selected step without any API calls", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.goto("/demo/learning");
  await expect(page.getByRole("heading", { name: "เรียนรู้ SOC ทีละขั้น" })).toBeVisible();
  await expect(page.getByText("3 ระดับ · 9 บทเรียน · 45 ขั้น จาก curriculum-v1.json")).toBeVisible();
  const catalog = page.getByRole("complementary", { name: "สารบัญบทเรียน" });
  const links = await catalog.getByRole("link").evaluateAll((items) => items.map((item) => ({ title: item.textContent!, href: item.getAttribute("href")! })));
  expect(links).toHaveLength(9);
  for (const lesson of links) {
    await page.goto(lesson.href);
    await expect(page.getByRole("heading", { name: lesson.title, exact: true })).toBeVisible();
    const advance = page.getByRole("button", { name: "เข้าใจแล้ว ไปขั้นถัดไป" });
    await expect(advance).toBeDisabled();
    for (let step = 1; step <= 5; step += 1) {
      await expect(page.getByText(`ขั้น ${step} / 5`, { exact: true })).toBeVisible();
      await page.getByRole("button", { name: /^กดดู:/ }).click();
      await expect(page.getByRole("heading", { name: "สิ่งที่ยังสรุปไม่ได้", exact: true })).toBeVisible();
      if (step < 5) await advance.click();
    }
  }
  const selectedUrl = page.url();
  await page.reload();
  await expect(page.getByText("ขั้น 5 / 5", { exact: true })).toBeVisible();
  expect(page.url()).toBe(selectedUrl);
  await expect(page.getByRole("button", { name: /^กดดู:/ })).toHaveAttribute("aria-expanded", "false");
  expect(apiRequests).toEqual([]);
});

test("mixed practice keeps case drafts in memory, escapes event text, and never pretends to grade or call AI", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.goto("/demo/learning?view=practice");
  await expect(page.getByRole("heading", { name: "ฝึกอ่านหลักฐานรวม", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "ตรวจความครบของร่าง (ไม่ให้คะแนน)" }).click();
  await expect(page.getByText("ยังขาดข้อมูล:")).toBeVisible();
  await page.getByRole("checkbox").first().check();
  await page.getByLabel("Severity", { exact: true }).selectOption("low");
  await page.getByLabel("Disposition", { exact: true }).selectOption("undetermined");
  await page.getByLabel("เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ").fill("พบคำขอที่ล้มเหลว ยังไม่พบหลักฐาน session สำเร็จในชุดที่ตรวจ");
  await page.getByRole("button", { name: "ตรวจความครบของร่าง (ไม่ให้คะแนน)" }).click();
  await expect(page.getByText(/กรอกช่องที่จำเป็นครบแล้ว แต่ยังไม่ได้ตรวจความถูกต้อง/)).toBeVisible();
  await page.getByRole("button", { name: "เทียบกิจกรรมกับขอบเขตงาน", exact: true }).click();
  await expect(page.locator("pre").filter({ hasText: "/training/<sample>" })).toBeVisible();
  await expect(page.locator("sample")).toHaveCount(0);
  await page.getByRole("button", { name: "อ่านผลของคำขอเข้าสู่ระบบ", exact: true }).click();
  await expect(page.getByLabel("เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ")).toHaveValue(/พบคำขอที่ล้มเหลว/);
  await page.getByRole("button", { name: "เปิดคำแนะนำจากบทเรียน" }).click();
  await expect(page.getByRole("link", { name: /^อ่านบทเรียนอ้างอิง:/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "ถาม AI — ยังไม่เชื่อม Dify" })).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel("เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ")).toHaveValue("");
  expect(apiRequests).toEqual([]);
});

test("preview supports 375/768/1440px and explains the pre-submit AI boundary", async ({ page }) => {
  await page.goto("/demo/learning");
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { name: "เรียนรู้ SOC ทีละขั้น" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByLabel("เลือกบทเรียนจากไฟล์").selectOption("15000000-0000-4000-8000-000000000302");
  await expect(page.getByRole("heading", { name: "ตั้งคำอธิบายอย่างน้อยสองทาง", exact: true })).toBeVisible();
  const target = page.getByRole("button", { name: /^กดดู:/ });
  await target.focus();
  await page.keyboard.press("Enter");
  await expect(target).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("link", { name: "ฝึกอ่านหลักฐานรวม", exact: true }).click();
  await page.getByLabel("เลือกกลุ่มตัวอย่าง").selectOption("3");
  await expect(page.getByRole("heading", { name: "ตรวจปริมาณอ่านที่ต่างจาก baseline", exact: true })).toBeVisible();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByRole("link", { name: "AI / RAG ใช้ตอนไหน", exact: true }).click();
  await expect(page.getByText("ระหว่างสอบ ก่อนส่ง:", { exact: true })).toBeVisible();
  await expect(page.getByText(/ไม่เปิด Ask AI ไม่แสดงคำใบ้หรือเฉลย/)).toBeVisible();
  await expect(page.getByRole("button", { name: "ถาม AI — ยังไม่เชื่อม Dify" })).toBeDisabled();
});
