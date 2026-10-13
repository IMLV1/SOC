import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("built browser assets contain no server fixture or truth payloads", async () => {
  const root = new URL("../.next/static/", import.meta.url);
  const files = await readdir(root, { recursive: true });
  const scripts = files.filter(path => path.endsWith(".js"));
  assert.ok(scripts.length > 0);
  for (const path of scripts) {
    const source = await readFile(new URL(path.replaceAll("\\", "/"), root), "utf8");
    assert.doesNotMatch(source, /SIM-T-204|CHG-T-404|records\/export|expected_evidence_keys|threat_label|account_owner_denied_activity/);
  }
});
