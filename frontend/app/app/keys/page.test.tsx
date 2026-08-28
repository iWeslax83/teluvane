import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import KeysPage from "./page";

const push = vi.fn();
const apiFetch = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/app/keys",
}));

vi.mock("@/lib/useSession", () => ({
  useSession: () => ({ token: "test-token", loading: false }),
}));

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

beforeEach(() => {
  apiFetch.mockReset();
  push.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("KeysPage", () => {
  it("lists existing keys and lets you revoke one", async () => {
    apiFetch.mockResolvedValueOnce([{ id: 1, name: "prod", prefix: "tv_live_ab12", revoked_at: null }]);
    render(<KeysPage />);
    await waitFor(() => expect(screen.getByText("prod")).toBeTruthy());
    expect(apiFetch).toHaveBeenCalledWith("/keys", { token: "test-token" });

    apiFetch.mockResolvedValueOnce({});
    apiFetch.mockResolvedValueOnce([{ id: 1, name: "prod", prefix: "tv_live_ab12", revoked_at: "2026-01-01" }]);
    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));
    await waitFor(() => expect(screen.getByText("revoked")).toBeTruthy());
  });

  it("shows the created key once and lets the user create a new one", async () => {
    apiFetch.mockResolvedValueOnce([]);
    render(<KeysPage />);
    await waitFor(() => expect(screen.getByText(/no keys yet/i)).toBeTruthy());

    fireEvent.change(screen.getByPlaceholderText(/key name/i), { target: { value: "staging" } });
    apiFetch.mockResolvedValueOnce({ key: "tv_live_abcdef" });
    apiFetch.mockResolvedValueOnce([{ id: 2, name: "staging", prefix: "tv_live_cd34", revoked_at: null }]);
    fireEvent.click(screen.getByRole("button", { name: /create key/i }));

    await waitFor(() => expect(screen.getByText("tv_live_abcdef")).toBeTruthy());
  });
});
