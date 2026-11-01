import { expect, test, type Page } from "@playwright/test";

const a = "33000000-0000-4000-8000-000000000001";
const b = "33000000-0000-4000-8000-000000000002";
const c = "33000000-0000-4000-8000-000000000003";
function deferred() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}
async function mockRuns(page: Page) {
  const state = { user: "account-a", sessions: 0, list: 0, hold: null as ReturnType<typeof deferred> | null };
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/auth/session")) {
      state.sessions++;
      return route.fulfill({ json: { data: { csrf_token: "test-only", expires_at: "2099-01-01T00:00:00Z",
        user: { id: state.user, role: "analyst", status: "active", display_name: `${state.user}-${state.sessions}` } } } });
    }
    if (url.pathname.endsWith("/scenarios")) return route.fulfill({ json: { data: [{ id: a, title: "S02 training", duration_ms: 75000 }] } });
    if (url.pathname.endsWith("/runs")) {
      state.list++;
      const owner = state.user;
      const hold = state.hold;
      const id = owner === "account-b" ? c : url.searchParams.has("cursor") ? b : a;
      if (hold) { state.hold = null; await hold.promise; }
      return route.fulfill({ json: { data: [{ id, status: "completed", elapsed_ms: 75000, duration_ms: 75000,
        server_time: "2026-11-01T00:00:00Z", analysis_mode: "real", version: 1 }],
        meta: { request_id: "review-only", next_cursor: id === a ? "page-two" : null } } });
    }
    return route.abort();
  });
  return state;
}

test("same-account focus and minute refresh preserve mounted paginated history", async ({ page }) => {
  await page.clock.install();
  const state = await mockRuns(page);
  await page.goto("/runs");
  await page.getByRole("button", { name: "โหลดรอบเพิ่มเติม", exact: true }).click();
  await expect(page.locator(`a[href='/runs/${b}']`)).toBeVisible();
  const originalLoads = state.list;
  const originalLink = await page.locator(`a[href='/runs/${b}']`).elementHandle();
  for (const trigger of ["focus", "minute"]) {
    const before = state.sessions;
    if (trigger === "focus") await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    else await page.clock.fastForward(60000);
    await expect.poll(() => state.sessions).toBeGreaterThan(before);
    await expect(page.getByRole("link", { name: `account-a-${state.sessions}`, exact: true })).toBeVisible();
    await expect(page.locator(`a[href='/runs/${b}']`)).toBeVisible();
    expect(await originalLink!.evaluate((node) => node.isConnected)).toBe(true);
    expect(state.list).toBe(originalLoads);
  }
});

test("late account-A response cannot replace account-B run history", async ({ page }) => {
  const state = await mockRuns(page);
  await page.goto("/runs");
  await expect(page.locator(`a[href='/runs/${a}']`)).toBeVisible();
  const gate = deferred();
  state.hold = gate;
  const request = page.waitForRequest((req) => new URL(req.url()).pathname === "/api/v1/runs");
  await page.getByRole("button", { name: "รีเฟรช", exact: true }).click();
  await request;
  state.user = "account-b";
  try {
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.locator(`a[href='/runs/${c}']`)).toBeVisible();
    const response = page.waitForResponse((res) => new URL(res.url()).pathname === "/api/v1/runs");
    gate.release();
    await response;
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.locator(`a[href='/runs/${a}']`)).toHaveCount(0);
    await expect(page.locator(`a[href='/runs/${c}']`)).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp("^account-b-") })).toBeVisible();
  } finally { gate.release(); }
});

test("manual refresh keeps the current history mounted while waiting", async ({ page }) => {
  const state = await mockRuns(page);
  await page.goto("/runs");
  const link = page.locator(`a[href='/runs/${a}']`);
  await expect(link).toBeVisible();
  const originalLink = await link.elementHandle();
  const gate = deferred();
  state.hold = gate;
  try {
    await page.getByRole("button", { name: "รีเฟรช", exact: true }).click();
    await expect(page.getByText("กำลังอัปเดตรายการ…", { exact: true })).toBeVisible();
    await expect(link).toBeVisible();
    expect(await originalLink!.evaluate((node) => node.isConnected)).toBe(true);
    await expect(page.getByRole("button", { name: "รีเฟรช", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "โหลดรอบเพิ่มเติม", exact: true })).toBeDisabled();
  } finally { gate.release(); }
  await expect(page.getByRole("button", { name: "รีเฟรช", exact: true })).toBeEnabled();
  expect(await originalLink!.evaluate((node) => node.isConnected)).toBe(true);
});
