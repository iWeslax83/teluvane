import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BillingPage from "./page";

const push = vi.fn();
const replace = vi.fn();
const apiFetch = vi.fn();
const getUser = vi.fn().mockResolvedValue({ data: { user: { email: "me@example.com" } } });

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(""),
  usePathname: () => "/app/billing",
}));

vi.mock("@/lib/useSession", () => ({
  useSession: () => ({ token: "test-token", loading: false }),
}));

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ auth: { getUser } }),
}));

beforeEach(() => {
  apiFetch.mockReset();
  push.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("BillingPage", () => {
  it("shows the free plan with both upgrade buttons", async () => {
    apiFetch.mockImplementation((path: string) => {
      if (path === "/billing/plan") return Promise.resolve({ plan: "free" });
      if (path === "/billing/usage") return Promise.resolve({ hosted_audits_used: 3, limit: 0 });
      throw new Error(`unexpected path ${path}`);
    });
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByText("free")).toBeTruthy());
    expect(screen.getByRole("button", { name: /upgrade to starter/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /upgrade to pro/i })).toBeTruthy();
  });

  it("shows manage subscription and an upgrade-to-pro nudge for a starter plan", async () => {
    apiFetch.mockImplementation((path: string) => {
      if (path === "/billing/plan") return Promise.resolve({ plan: "starter" });
      if (path === "/billing/usage") return Promise.resolve({ hosted_audits_used: 5, limit: 15 });
      throw new Error(`unexpected path ${path}`);
    });
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByText("starter")).toBeTruthy());
    expect(screen.getByText(/5 \/ 15/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /manage subscription/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /upgrade to pro/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /upgrade to starter/i })).toBeNull();
  });

  it("shows only manage subscription for a pro plan", async () => {
    apiFetch.mockImplementation((path: string) => {
      if (path === "/billing/plan") return Promise.resolve({ plan: "pro" });
      if (path === "/billing/usage") return Promise.resolve({ hosted_audits_used: 10, limit: 50 });
      throw new Error(`unexpected path ${path}`);
    });
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByText("pro")).toBeTruthy());
    expect(screen.getByRole("button", { name: /manage subscription/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /upgrade to pro/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /upgrade to starter/i })).toBeNull();
  });

  it("redirects to checkout with the chosen plan on upgrade", async () => {
    apiFetch.mockImplementation((path: string, opts?: { method?: string; body?: { plan?: string } }) => {
      if (path === "/billing/plan") return Promise.resolve({ plan: "free" });
      if (path === "/billing/usage") return Promise.resolve({ hosted_audits_used: 0, limit: 0 });
      if (path === "/billing/checkout" && opts?.method === "POST") {
        expect(opts.body?.plan).toBe("pro");
        return Promise.resolve({ url: "https://checkout.example/session" });
      }
      throw new Error(`unexpected path ${path}`);
    });
    const original = window.location;
    // @ts-expect-error jsdom location is not directly writable
    delete window.location;
    // @ts-expect-error assigning a minimal stub for the redirect assertion
    window.location = { href: "" };

    render(<BillingPage />);
    await waitFor(() => expect(screen.getByText("free")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /upgrade to pro/i }));
    await waitFor(() => expect(window.location.href).toBe("https://checkout.example/session"));

    window.location = original;
  });
});
