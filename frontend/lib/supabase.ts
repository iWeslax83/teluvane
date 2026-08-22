import { createClient, SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;
let _rememberMe = true;

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
