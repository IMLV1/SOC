export function publicSupabaseConfig(url: string | undefined, key: string | undefined) {
  if (!url || !key) throw new Error("Supabase public configuration is missing.");
  let parsed: URL;
  try { parsed = new URL(url); }
  catch { throw new Error("Supabase project URL is invalid."); }
  if (parsed.protocol !== "https:" || !/^[a-z0-9]{20}\.supabase\.co$/.test(parsed.hostname)
    || parsed.port || parsed.username || parsed.password || parsed.search || parsed.hash
    || parsed.pathname !== "/") {
    throw new Error("A standard HTTPS Supabase project URL is required.");
  }
  // Accept only the intended public key type, never legacy JWT/service_role/secret keys.
  if (!/^sb_publishable_[A-Za-z0-9_-]{10,}$/.test(key)) {
    throw new Error("A Supabase publishable key is required, not a server secret.");
  }
  return { url: parsed.origin, key };
}
