import { expect, test } from "@playwright/test";

test("Ask AI keeps conflict draft, escapes source and hides withdrawn projections", async ({ page }) => {
  const run = "11111111-1111-4111-8111-111111111111";
  const ticket = "22222222-2222-4222-8222-222222222222";
  const analysis = "33333333-3333-4333-8333-333333333333";
  const item = "44444444-4444-4444-8444-444444444444";
  let conflict = true, withdrawn = false, posted = false;
  const citation = { retrieval_item_id: item, document_title: "Reviewed guide", document_version: "1",
    heading: "Evidence", excerpt: "<script>window.sourceInjected=true</script>", content_hash: "a".repeat(64) };
  const result = { id: analysis, run_id: run, retry_of: null, mode: "mock", model_id: "mock-v1",
    prompt_version: "rag-v1", status: "succeeded", version: 2, evidence_ids: [], kind: "question",
    question_text: "Question", response_visibility: "visible", error_code: null, usage: null,
    created_at: new Date().toISOString(), finished_at: new Date().toISOString(),
    retrieval: { status: "matched", release_id: run, config_version: "test", citations: [citation] },
    result: { answer: "Guidance only", claims: [], unknowns: [], answer_status: "answered", evidence_truncated: false } };
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith("/auth/session")) data = { csrf_token: "test", expires_at: new Date().toISOString(),
      user: { id: ticket, display_name: "Analyst", email: "test@example.test", role: "analyst", status: "active" } };
    else if (path.endsWith("/auth/csrf")) data = { csrf_token: "test" };
    else if (path.endsWith("/questions")) {
      if (conflict) { conflict = false; await route.fulfill({ status: 409, json: { error: { code: "VERSION_CONFLICT" } } }); return; }
      posted = true; data = result;
    } else if (path.includes("/sources/")) data = citation;
    else if (path.endsWith("/analyses")) data = !posted ? [] : [withdrawn ? {
      ...result, result: null, question_text: null, response_visibility: "withdrawn",
      retrieval: { ...result.retrieval, status: "revoked", citations: [] } } : result];
    else if (path.endsWith(`/tickets/${ticket}`)) data = { id: ticket, run_id: run, title: "Investigation",
      severity: "low", status: "open", version: 1, deleted_at: null, evidence_ids: [], latest_assessment: null };
    else if (path.endsWith(`/runs/${run}`)) data = { id: run, status: "running", version: 1, analysis_mode: "mock" };
    await route.fulfill({ json: { data, meta: { request_id: "test" } } });
  });
  await page.goto(`/runs/${run}/tickets/${ticket}`);
  await page.getByLabel("คำถามเกี่ยวกับ ticket").fill("Keep my draft");
  await page.getByRole("button", { name: "ถาม AI", exact: true }).click();
  await expect(page.getByText("ข้อมูลเปลี่ยนหรือแหล่งถูกถอน ร่างคำถามยังอยู่")).toBeVisible();
  await expect(page.getByLabel("คำถามเกี่ยวกับ ticket")).toHaveValue("Keep my draft");
  await page.getByRole("button", { name: "ถาม AI", exact: true }).click();
  await expect(page.getByText("Guidance only", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reviewed guide · 1" }).click();
  await expect(page.getByRole("dialog", { name: "แหล่งอ้างอิง" })).toContainText("<script>");
  expect(await page.evaluate(() => "sourceInjected" in window)).toBe(false);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  withdrawn = true;
  await expect(page.getByText("คำตอบถูกถอนแล้ว")).toBeVisible();
  await expect(page.getByRole("dialog", { name: "แหล่งอ้างอิง" })).toHaveCount(0);
  await expect(page.getByText("Guidance only", { exact: true })).toHaveCount(0);
});
