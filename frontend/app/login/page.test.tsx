import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LoginPage from "./page";

const signInWithPassword = vi.fn().mockResolvedValue({ error: null });
const signUp = vi.fn();
vi.mock("@/lib/supabase", () => ({
  getSupabase: () => ({ auth: { signInWithPassword, signUp, resetPasswordForEmail: vi.fn() } }),
  setRememberMe: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => {
  signInWithPassword.mockClear();
  signUp.mockClear();
});

describe("LoginPage remember me", () => {
  it("defaults to checked", () => {
    render(<LoginPage />);
    expect((screen.getByLabelText(/remember me/i) as HTMLInputElement).checked).toBe(true);
  });

  it("calls setRememberMe(false) on submit when unchecked", async () => {
    const { setRememberMe } = await import("@/lib/supabase");
    render(<LoginPage />);
    fireEvent.change(screen.getByPlaceholderText("you@company.com"), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: "password123" } });
    fireEvent.click(screen.getByLabelText(/remember me/i));
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(setRememberMe).toHaveBeenCalledWith(false);
  });
});

describe("LoginPage password visibility", () => {
  it("hides the password by default and reveals it on toggle click", () => {
    render(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText("••••••••") as HTMLInputElement;
    expect(passwordInput.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: /show password/i }));
    expect(passwordInput.type).toBe("text");
    fireEvent.click(screen.getByRole("button", { name: /hide password/i }));
    expect(passwordInput.type).toBe("password");
  });
});

describe("LoginPage inline validation", () => {
  it("shows a specific message for a too-short signup password without calling the network", async () => {
    const { getSupabase } = await import("@/lib/supabase");
    const signUp = (getSupabase() as any).auth.signUp;
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /sign up$/i })); // switch to signup mode
    fireEvent.change(screen.getByPlaceholderText("you@company.com"), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: /^sign up$/i }));
    expect(await screen.findByText(/password must be at least 6 characters/i)).toBeTruthy();
    expect(signUp).not.toHaveBeenCalled();
  });
});
