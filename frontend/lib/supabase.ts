import { createClient, SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;
const REMEMBER_ME_KEY = "tv-remember-me";
// The preference itself lives in localStorage (under REMEMBER_ME_KEY) so it survives a full page
// reload, independent of where the session token ends up. "0" means off, anything else (including
// the key being absent) means on, matching the historical default.
let _rememberMe = typeof window === "undefined" ? true : window.localStorage.getItem(REMEMBER_ME_KEY) !== "0";

// Supabase persists the session through whichever Storage-like object we hand it. Reading
// `_rememberMe` inside each method (rather than capturing it once) lets setRememberMe() change
// the target storage for the client that's already been created as a singleton.
const _dynamicStorage = {
  getItem: (key: string) => (_rememberMe ? window.localStorage : window.sessionStorage).getItem(key),
  setItem: (key: string, value: string) => (_rememberMe ? window.localStorage : window.sessionStorage).setItem(key, value),
  removeItem: (key: string) => (_rememberMe ? window.localStorage : window.sessionStorage).removeItem(key),
};

export function setRememberMe(remember: boolean): void {
  _rememberMe = remember;
  window.localStorage.setItem(REMEMBER_ME_KEY, remember ? "1" : "0");
}

export function getSupabase(): SupabaseClient {
  if (!_client) {
    _client = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      { auth: { persistSession: true, autoRefreshToken: true, storage: _dynamicStorage } },
    );
  }
  return _client;
}
