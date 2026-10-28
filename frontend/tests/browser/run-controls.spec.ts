import { expect, test } from "@playwright/test";

for (const failure of [
  { status: 503, code: "AUTH_REFRESH_PENDING" },
  { status: 401, code: "AUTH_REQUIRED" },
]) {
  test(`pause failure ${failure.code} survives polling and allows an explicit retry`, async ({ page }) => {
    const id = "00000000-0000-4000-8000-000000000005";
    let fail = true;
    let posts = 0;
    let reads = 0;
    let run = { id, status: "running", version: 1, elapsed_ms: 5000, duration_ms: 75000,
      server_time: "2026-10-29T00:00:00Z", expires_at: "2099-01-01T00:00:00Z", seed: 1, analysis_mode: "mock" };
    await page.route("**/api/**", async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path === "/api/v1/auth/session") return route.fulfill({ json: { data: {
        csrf_token: "test-only", expires_at: "2099-01-01T00:00:00Z", user: {
          id, display_name: "Control test", email: "control@example.test", role: "analyst", status: "active",
        },
      } } });
      if (path === "/api/v1/auth/csrf") return route.fulfill({ json: { data: { csrf_token: "test-only" } } });
      if (path === `/api/v1/runs/${id}`) {
        reads++;
        return route.fulfill({ json: { data: run } });
      }
      if (path.endsWith("/pause") || path.endsWith("/resume")) {
        posts++;
        expect(request.postDataJSON()).toEqual({ expected_version: run.version });
        if (fail) return route.fulfill({ status: failure.status, json: { error: { code: failure.code } } });
        run = { ...run, status: path.endsWith("/pause") ? "paused" : "running", version: run.version + 1 };
        return route.fulfill({ json: { data: run } });
      }
      return route.fulfill({ json: { data: [], meta: { next_cursor: null } } });
    });
    await page.goto(`/runs/${id}`);
    await page.getByRole("button", { name: "พักรอบ", exact: true }).click();
    const error = page.getByRole("main").getByRole("alert");
    await expect(error).toBeVisible();
    const readsAfterError = reads;
    await expect.poll(() => reads).toBeGreaterThan(readsAfterError);
    await expect(error).toBeVisible();
    expect(posts).toBe(1);
    fail = false;
    await page.getByRole("button", { name: "พักรอบ", exact: true }).click();
    await expect(page.getByRole("button", { name: "ทำต่อ", exact: true })).toBeVisible();
    await expect(error).toBeHidden();
    await page.reload();
    await page.getByRole("button", { name: "ทำต่อ", exact: true }).click();
    await expect(page.getByRole("button", { name: "พักรอบ", exact: true })).toBeVisible();
    expect(posts).toBe(3);
  });
}