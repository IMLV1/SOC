import { expect, test } from "@playwright/test";

const id = "00000000-0000-4000-8000-000000000077";
const session = {
  user: {
    id,
    display_name: "UI test",
    email: "ui@example.test",
    role: "analyst",
    status: "active",
  },
  expires_at: "2099-01-01T00:00:00Z",
  csrf_token: "test",
};
const run = {
  id,
  status: "running",
  version: 1,
  elapsed_ms: 0,
  duration_ms: 75000,
  expires_at: "2099-01-01T00:00:00Z",
  server_time: "2026-10-14T00:00:00Z",
  seed: 42,
  analysis_mode: "mock",
};

test("cursor drains before after_seq; evidence is escaped; filters survive refresh", async ({
  page,
}) => {
  const queries: URLSearchParams[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    let data: unknown = [];
    let next_cursor: string | null = null;
    if (url.pathname.endsWith("/auth/session")) data = session;
    else if (url.pathname.endsWith(`/runs/${id}`)) data = run;
    else if (url.pathname.endsWith("/events")) {
      queries.push(url.searchParams);
      const seq = url.searchParams.has("cursor") ? 2 : 1;
      if (
        !url.searchParams.has("cursor") &&
        url.searchParams.get("after_seq") === "0"
      )
        next_cursor = "next-page";
      data = [
        {
          id: `${id.slice(0, -1)}${seq}`,
          run_id: id,
          release_seq: seq,
          source: "web",
          asset_id: "PORTAL-01",
          username: "member",
          src_ip: "192.0.2.1",
          event_time: run.server_time,
          ingested_at: run.server_time,
          request: { path: "<script>window.leaked=true</script>" },
          response: { status: 200 },
          log: { message: "<img src=x onerror=alert(1)>" },
        },
      ];
    }
    await route.fulfill({
      json: { data, meta: { request_id: "test", next_cursor } },
    });
  });
  await page.goto(`/runs/${id}?asset_id=PORTAL-01&src_ip=192.0.2.1`);
  await expect(page.locator(".event-list button")).toHaveCount(2);
  expect(
    queries.some((query) => query.has("cursor") && !query.has("after_seq")),
  ).toBe(true);
  await page.locator(".event-list button").first().click();
  await expect(page.locator("pre").first()).toContainText("<script>");
  expect(await page.evaluate(() => "leaked" in window)).toBe(false);
  await page.reload();
  await expect(page.getByLabel("Asset", { exact: true })).toHaveValue(
    "PORTAL-01",
  );
  await expect(page.getByLabel("Source IP", { exact: true })).toHaveValue(
    "192.0.2.1",
  );
  await expect(page.getByRole("heading", { name: "Request" })).toBeVisible();
});

test("loading, empty and expired-session states", async ({ page }) => {
  let expired = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session")) {
      await route.fulfill({ json: { data: session } });
      return;
    }
    if (expired) {
      await route.fulfill({
        status: 401,
        json: { error: { code: "AUTH_REQUIRED" } },
      });
      return;
    }
    if (path.endsWith(`/runs/${id}`)) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.fulfill({ json: { data: run } });
    } else
      await route.fulfill({ json: { data: [], meta: { next_cursor: null } } });
  });
  await page.goto(`/runs/${id}`);
  await expect(page.getByText("กำลังโหลดรอบและเหตุการณ์…")).toBeVisible();
  await expect(
    page.getByText(
      "ยังไม่มีเหตุการณ์ที่ตรงตัวกรอง ระบบจะตรวจอีกครั้งอัตโนมัติ",
    ),
  ).toBeVisible();
  expired = true;
  await expect(
    page.getByRole("alert").filter({ hasText: "เซสชันหมดอายุ" }),
  ).toBeVisible({ timeout: 10000 });
});

test("temporary failure backs off then recovers", async ({ page }) => {
  let failedAt = 0;
  let recoveredAt = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session")) {
      await route.fulfill({ json: { data: session } });
      return;
    }
    if (path.endsWith(`/runs/${id}`)) {
      if (!failedAt) {
        failedAt = Date.now();
        await route.fulfill({
          status: 503,
          json: { error: { code: "SERVICE_UNAVAILABLE" } },
        });
        return;
      }
      recoveredAt = Date.now();
      await route.fulfill({ json: { data: run } });
    } else
      await route.fulfill({ json: { data: [], meta: { next_cursor: null } } });
  });
  await page.goto(`/runs/${id}`);
  await expect(
    page.getByRole("alert").filter({ hasText: "ระบบจะลองใหม่" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "พักรอบ" })).toBeVisible({
    timeout: 10000,
  });
  expect(recoveredAt - failedAt).toBeGreaterThanOrEqual(3800);
});

test("run history follows cursor and keeps existing rows", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/auth/session")) {
      await route.fulfill({ json: { data: session } });
      return;
    }
    if (url.pathname.endsWith("/scenarios")) {
      await route.fulfill({ json: { data: [] } });
      return;
    }
    const next = url.searchParams.has("cursor");
    await route.fulfill({
      json: {
        data: [{ ...run, id: next ? `${id.slice(0, -1)}8` : id }],
        meta: { next_cursor: next ? null : "next-history" },
      },
    });
  });
  await page.goto("/runs");
  await page.getByRole("button", { name: "โหลดรอบเพิ่มเติม" }).click();
  await expect(page.locator(".run-list li")).toHaveCount(2);
  await expect(
    page.getByRole("button", { name: "โหลดรอบเพิ่มเติม" }),
  ).toHaveCount(0);
});
