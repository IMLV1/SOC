import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { publicSupabaseConfig } from "./config";

// Call per request from a cookie-writable Route Handler, passing its response headers.
// Not wired into the existing SOC login until identity migration is complete.
export async function createClient(responseHeaders: Headers) {
  const config = publicSupabaseConfig(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
  const cookieStore = await cookies();
  return createServerClient(config.url, config.key, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll(cookiesToSet, cacheHeaders) {
        // Do not silently drop refresh cookies in a read-only Server Component.
        for (const { name, value, options } of cookiesToSet) cookieStore.set(name, value, options);
        for (const [name, value] of Object.entries(cacheHeaders)) responseHeaders.set(name, value);
        responseHeaders.set("Cache-Control", "private, no-store");
      },
    },
  });
}
