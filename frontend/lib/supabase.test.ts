import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn((_url: string, _key: string, opts: any) => ({ __opts: opts })),
}));

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  sessionStorage.clear();
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

  it("defaults to localStorage when no preference key is set", async () => {
    expect(localStorage.getItem("tv-remember-me")).toBeNull();
    const { getSupabase } = await import("./supabase");
    const client: any = getSupabase();
    client.__opts.auth.storage.setItem("k4", "v4");
    expect(localStorage.getItem("k4")).toBe("v4");
    expect(sessionStorage.getItem("k4")).toBeNull();
  });

  it("persists the remember-me preference across a module reload", async () => {
    localStorage.setItem("tv-remember-me", "0");
    const { getSupabase } = await import("./supabase");
    const client: any = getSupabase();
    client.__opts.auth.storage.setItem("k3", "v3");
    expect(sessionStorage.getItem("k3")).toBe("v3");
    expect(localStorage.getItem("k3")).toBeNull();
  });
});
