"use client";

import { createBrowserClient } from "@supabase/ssr";
import { publicSupabaseConfig } from "./config";

export function createClient() {
  const config = publicSupabaseConfig(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
  // SSR cookie storage; do not add a second browser session store.
  return createBrowserClient(config.url, config.key);
}
