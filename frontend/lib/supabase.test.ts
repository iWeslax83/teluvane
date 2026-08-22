import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn((_url: string, _key: string, opts: any) => ({ __opts: opts })),
}));

beforeEach(() => {
  vi.resetModules();
  process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "anon-key";
});

describe("getSupabase storage", () => {
  it("writes to localStorage by default (remembered)", async () => {
    const { getSupabase } = await import("./supabase");
    const client: any = getSupabase();
    client.__opts.auth.storage.setItem("k", "v");
    expect(localStorage.getItem("k")).toBe("v");
    expect(sessionStorage.getItem("k")).toBeNull();
  });

  it("writes to sessionStorage after setRememberMe(false)", async () => {
    const { getSupabase, setRememberMe } = await import("./supabase");
    const client: any = getSupabase();
    setRememberMe(false);
    client.__opts.auth.storage.setItem("k2", "v2");
    expect(sessionStorage.getItem("k2")).toBe("v2");
    expect(localStorage.getItem("k2")).toBeNull();
  });
});
