import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("runtime learning surfaces use API, not public JSON or local storage", async () => {
  for (const path of ["src/app/learning/page.tsx", "src/app/practice/page.tsx", "src/app/knowledge-check/page.tsx"]) {
    const source = await readFile(new URL(`../${path}`, import.meta.url), "utf8");
    assert.match(source, /read</);
    assert.doesNotMatch(source, /localStorage|sessionStorage|public\/learning|practice-v1\.json|curriculum-v1\.json/);
  }
  const publicFiles = await readdir(new URL("../public/learning/", import.meta.url));
  assert.ok(!publicFiles.some((path) => path.endsWith(".json")));
});
