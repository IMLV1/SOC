import assert from "node:assert/strict";
import test from "node:test";

const origin = process.env.SOC_SMOKE_ORIGIN || "http://127.0.0.1:3000";

test("landing page loads without fixture assets or client secrets", async () => {
  const response = await fetch(origin);
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /SOC LEARNING LAB/);
  assert.match(html, /ยังไม่เปิดให้สอบจริง/);
  assert.doesNotMatch(html, /@demo\.test|localStorage|ground.truth|private_key/);
  const scripts = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(scripts.length > 0);
  for (const path of scripts) {
    const asset = await fetch(new URL(path, origin));
    assert.equal(asset.status, 200);
    assert.doesNotMatch(await asset.text(), /@demo\.test|private_key_ref|e1c99650-03ec/);
  }
});

test("same-origin health proxy preserves liveness and unavailable readiness", async () => {
  const live = await fetch(`${origin}/health/live`);
  assert.equal(live.status, 200);
  assert.equal((await live.json()).data.status, "alive");
  const ready = await fetch(`${origin}/health/ready`);
  assert.equal(ready.status, 503);
  assert.equal((await ready.json()).error.code, "SERVICE_UNAVAILABLE");
  assert.equal(ready.headers.get("cache-control"), "no-store");
});

test("draft domain routes reach backend but remain unavailable", async () => {
  const response = await fetch(`${origin}/api/v1/runs`, { method: "POST" });
  assert.equal(response.status, 404);
  assert.equal((await response.json()).error.code, "NOT_FOUND");
});
