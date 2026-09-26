import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import LandingBody from "./LandingBody";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" } }),
  IBM_Plex_Mono: () => ({ className: "", style: { fontFamily: "IBM Plex Mono" } }),
}));

beforeEach(() => {
  vi.stubGlobal("IntersectionObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
});

describe("LandingBody", () => {
  it("renders the hero, pricing, and footer sections", () => {
    render(<LandingBody />);
    expect(screen.getAllByRole("link", { name: /get started free/i }).length).toBeGreaterThan(0);
    expect(screen.getByText("$19.99")).toBeTruthy();
    expect(screen.getByText(/not legal advice/i)).toBeTruthy();
  });

  it("renders the hero at full opacity immediately, without waiting for IntersectionObserver", () => {
    const { container } = render(<LandingBody />);
    const opening = container.querySelector("#opening") as HTMLElement;
    expect(opening.style.opacity).toBe("1");
  });

  it("shows an MCP config the server can actually load", () => {
    render(<LandingBody />);
    expect(screen.getByText(/"command": "teluvane-mcp"/)).toBeTruthy();
    expect(screen.queryByText(/api\.teluvane\.com\/mcp/)).toBeNull();
  });

  it("carries no invented numbers or overstated claims", () => {
    const { container } = render(<LandingBody />);
    expect(container.textContent).not.toMatch(/4471|0\.94|multi-agent/i);
  });
});
