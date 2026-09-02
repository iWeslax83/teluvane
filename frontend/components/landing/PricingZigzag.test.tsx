import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PricingZigzag from "./PricingZigzag";

describe("PricingZigzag", () => {
  it("renders all four tiers with their prices", () => {
    render(<PricingZigzag />);
    expect(screen.getByText("$0")).toBeTruthy();
    expect(screen.getByText("$9.99")).toBeTruthy();
    expect(screen.getByText("$19.99")).toBeTruthy();
    expect(screen.getByText("Custom")).toBeTruthy();
  });

  it("sends the free and starter CTAs to signup, and enterprise to a real contact channel", () => {
    render(<PricingZigzag />);
    expect(screen.getAllByRole("link", { name: /get started/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /^get started$/i }).getAttribute("href")).toBe("/login");
    expect(screen.getByRole("link", { name: /contact us/i }).getAttribute("href")).toBe("mailto:hello@teluvane.com");
  });
});
