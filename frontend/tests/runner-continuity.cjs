// Explicit local acceptance: requires disposable soc-accept06 Compose stack.
const { chromium } = require("@playwright/test");
const { execFileSync } = require("node:child_process");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { randomUUID } = require("node:crypto");
const origin = "http://127.0.0.1:13006";
const docker = process.env.SOC_DOCKER_BIN || "docker";
process.env.SOC_WEB_PORT = "13006";
process.env.SOC_API_PORT = "18006";
process.env.SOC_DB_PORT = "55436";
function compose(args) {
  return execFileSync(docker, ["compose", "-p", "soc-accept06", ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}
function rows(run) {
  assert.match(run, /^[0-9a-f-]{36}$/);
  return JSON.parse(
    compose([
      "exec",
      "-T",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "soc",
      "-Atc",
      `SELECT json_build_object('status',r.status,'events',(SELECT count(*) FROM app.events WHERE run_id=r.id),'unique_events',(SELECT count(DISTINCT (scenario_instance_id,fixture_event_key)) FROM app.events WHERE run_id=r.id),'unique_seq',(SELECT count(DISTINCT release_seq) FROM app.events WHERE run_id=r.id),'jobs',(SELECT count(*) FROM app.jobs WHERE run_id=r.id),'unique_jobs',(SELECT count(DISTINCT dedupe_key) FROM app.jobs WHERE run_id=r.id)) FROM app.runs r WHERE id='${run}'`,
    ]),
  );
}
async function waitFor(run, predicate, timeout = 25000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    const row = rows(run);
    if (predicate(row)) return row;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Runner acceptance timeout");
}
(async () => {
  let browser;
  try {
    browser = await chromium.launch();
    const context = await browser.newContext({ baseURL: origin });
    const page = await context.newPage();
    await page.goto("/register");
    const email = `continuity-${Date.now()}@example.test`,
      password = randomUUID().slice(0, 10);
    await page.getByLabel("ชื่อที่แสดง").fill("Continuity test");
    await page.getByLabel("อีเมล", { exact: true }).fill(email);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
    await page.getByRole("button", { name: "สร้างบัญชี Analyst" }).click();
    await page.getByRole("link", { name: "ไปเข้าสู่ระบบ" }).click();
    await page.getByLabel("อีเมล", { exact: true }).fill(email);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
    await page
      .getByRole("button", { name: "เข้าสู่ระบบ", exact: true })
      .click();
    await page.waitForURL("**/account");
    const csrf = (await (await context.request.get("/api/v1/auth/csrf")).json())
      .data.csrf_token;
    const catalog = (
      await (await context.request.get("/api/v1/scenarios")).json()
    ).data;
    const response = await context.request.post("/api/v1/runs", {
      data: { scenario_ids: [catalog[0].id], seed: 42 },
      headers: {
        Origin: origin,
        "X-CSRF-Token": csrf,
        "Idempotency-Key": require("node:crypto").randomUUID(),
      },
    });
    assert.equal(response.status(), 201);
    const run = (await response.json()).data.id;
    const started = await waitFor(run, (row) => row.events > 0);
    const logout = await context.request.post("/api/v1/auth/logout", {
      data: {},
      headers: { Origin: origin, "X-CSRF-Token": csrf },
    });
    assert.equal(logout.status(), 204);
    assert.equal((await context.request.get("/api/v1/me")).status(), 401);
    const afterLogout = await waitFor(
      run,
      (row) => row.events > started.events,
    );
    await browser.close();
    browser = null;
    const afterClose = await waitFor(
      run,
      (row) => row.events > afterLogout.events,
    );
    compose(["restart", "worker"]);
    const final = await waitFor(
      run,
      (row) => row.status === "reviewing",
      95000,
    );
    assert.equal(final.events, 15);
    assert.equal(final.unique_events, final.events);
    assert.equal(final.unique_seq, final.events);
    assert.equal(final.unique_jobs, final.jobs);
    const evidence = {
      run_id: run,
      started,
      after_logout: afterLogout,
      after_browser_close: afterClose,
      after_worker_restart: final,
    };
    fs.mkdirSync("test-results", { recursive: true });
    fs.writeFileSync(
      "test-results/runner-continuity.json",
      JSON.stringify(evidence, null, 2),
    );
    console.log(JSON.stringify(evidence));
  } finally {
    if (browser) await browser.close();
  }
})().catch(() => {
  console.error("Runner continuity acceptance failed.");
  process.exitCode = 1;
});
