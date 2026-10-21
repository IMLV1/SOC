import { expect, test } from "@playwright/test";

test("finish training freezes evaluation and exposes the JSON export", async ({
  page,
}) => {
  test.setTimeout(120000);
  const email = `evaluation-${Date.now()}@example.test`;
  const password = crypto.randomUUID().slice(0, 10);
  await page.goto("/register");
  await page.getByLabel("ชื่อที่แสดง").fill("Evaluation Runner");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
  await expect(page).toHaveURL(/\/account$/);
  await page.goto("/runs");
  await page.getByRole("button", { name: "เริ่มรอบฝึก" }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "จบรอบและประเมินผล" }).click();
  await expect(page.getByRole("link", { name: "ดูผลประเมิน" })).toBeVisible();
  await page.getByRole("link", { name: "ดูผลประเมิน" }).click();
  await expect(
    page.getByRole("heading", { name: "ผลประเมินรอบฝึก" }),
  ).toBeVisible();
  await expect(page.getByText(/Snapshot SHA-256:/)).toBeVisible({
    timeout: 90000,
  });
  await expect(
    page.getByRole("link", { name: "ดาวน์โหลด JSON snapshot" }),
  ).toHaveAttribute("href", new RegExp(`/api/v1/runs/[0-9a-f-]+/export`));
  const exportResponse = await page.request.get(
    (await page
      .getByRole("link", { name: "ดาวน์โหลด JSON snapshot" })
      .getAttribute("href")) ?? "",
  );
  expect(exportResponse.status()).toBe(200);
  const exported = await exportResponse.json();
  expect(exported.run_id).toMatch(/^[0-9a-f-]+$/);
  expect(exported.snapshot.truth_versions).toBeDefined();
  expect(JSON.stringify(exported)).not.toContain("explanation");
});
