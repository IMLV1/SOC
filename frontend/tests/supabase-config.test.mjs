import assert from "node:assert/strict";
import test from "node:test";
import { publicSupabaseConfig } from "../src/utils/supabase/config.ts";

const url = "https://abcdefghijklmnopqrst.supabase.co";
const key = "sb_publishable_test_only_not_a_real_key";

test("public config accepts only a standard HTTPS project and publishable key", () => {
  assert.deepEqual(publicSupabaseConfig(`${url}/`, key), { url, key });
});

for (const invalid of [undefined, "", "http://abcdefghijklmnopqrst.supabase.co", `${url}/auth/v1`, `${url}?key=value`, "https://abcdefghijklmnopqrst.supabase.co.attacker.test", "https://user:password@abcdefghijklmnopqrst.supabase.co"]) {
  test(`public config rejects invalid URL variant ${String(invalid)}`, () => {
    assert.throws(() => publicSupabaseConfig(invalid, key));
  });
}

for (const invalid of [undefined, "", "sb_secret_test_only_not_a_real_key", "service_role", "eyJhbGciOiJIUzI1NiJ9.test-only.signature"]) {
  test(`public config rejects missing or non-publishable key ${String(invalid)}`, () => {
    assert.throws(() => publicSupabaseConfig(url, invalid));
  });
}

test("configuration errors do not echo credentials or key values", () => {
  const secret = "sb_secret_private_test_only";
  assert.throws(() => publicSupabaseConfig(url, secret), (error) => !error.message.includes(secret));
});
