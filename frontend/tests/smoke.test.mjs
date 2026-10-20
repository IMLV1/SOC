import assert from "node:assert/strict";
import test from "node:test";

const origin = process.env.SOC_SMOKE_ORIGIN || "http://127.0.0.1:3000";

// Check rendered HTML and downloaded scripts for fixture data or secret-like values.
test("landing page loads without fixture assets or client secrets", async () => {
  const response = await fetch(origin);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /SOC LEARNING LAB/);
  assert.match(html, /พื้นที่ฝึกจากข้อมูลจำลอง/);
  assert.doesNotMatch(
    html,
    /@demo\.test|localStorage|ground.truth|private_key/,
  );
  const scripts = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map(
    (m) => m[1],
  );
  assert.ok(scripts.length > 0);
  for (const path of scripts) {
    const asset = await fetch(new URL(path, origin));
    assert.equal(asset.status, 200);
    assert.doesNotMatch(
      await asset.text(),
      /@demo\.test|private_key_ref|e1c99650-03ec/,
    );
  }
});

// Liveness and readiness differ: the app may live while required dependencies are unavailable.
test("same-origin health proxy preserves liveness and configured readiness", async () => {
  const live = await fetch(`${origin}/health/live`);
  assert.equal(live.status, 200);
  assert.equal((await live.json()).data.status, "alive");
  const ready = await fetch(`${origin}/health/ready`);
  const expected = Number(process.env.SOC_EXPECT_READY_STATUS || "503");
  assert.ok([200, 503].includes(expected));
  assert.equal(ready.status, expected);
  const body = await ready.json();
  if (expected === 200) assert.equal(body.data.status, "ready");
  else assert.equal(body.error.code, "SERVICE_UNAVAILABLE");
  assert.equal(ready.headers.get("cache-control"), "no-store");
});

// Anonymous callers must reach the API boundary and be rejected by authentication.
test("run routes reach backend and require a session", async () => {
  const response = await fetch(`${origin}/api/v1/runs`);
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error.code, "AUTH_REQUIRED");
});
