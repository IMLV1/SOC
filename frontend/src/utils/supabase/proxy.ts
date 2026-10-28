import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import type { CookieOptions } from "@supabase/ssr";
import { publicSupabaseConfig } from "./config";

// Prepared helper, not a root proxy: existing sessions/routes remain unchanged.
// Refreshing a Supabase session alone does not authorize any SOC resource.
export async function updateSession(request: NextRequest) {
  const config = publicSupabaseConfig(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
  const pendingCookies = new Map<string, { name: string; value: string; options: CookieOptions }>();
  const cacheHeaders: Record<string, string> = {};
  const supabase = createServerClient(config.url, config.key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet, headers) {
        for (const cookie of cookiesToSet) {
          request.cookies.set(cookie.name, cookie.value);
          pendingCookies.set(cookie.name, cookie);
        }
        Object.assign(cacheHeaders, headers);
      },
    },
  });
  await supabase.auth.getClaims();
  const response = NextResponse.next({ request });
  for (const { name, value, options } of pendingCookies.values()) response.cookies.set(name, value, options);
  for (const [name, value] of Object.entries(cacheHeaders)) response.headers.set(name, value);
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
