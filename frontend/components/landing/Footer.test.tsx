import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Footer from "./Footer";

describe("Footer", () => {
  it("links to contact, blog, dashboard, privacy, terms, and accessibility", () => {
    render(<Footer />);
    expect(screen.getByRole("link", { name: /contact/i }).getAttribute("href")).toBe("mailto:hello@teluvane.com");
    expect(screen.getByRole("link", { name: /blog/i }).getAttribute("href")).toBe("/blog");
    expect(screen.getByRole("link", { name: /dashboard/i }).getAttribute("href")).toBe("/login");
    expect(screen.getByRole("link", { name: /privacy/i }).getAttribute("href")).toBe("/privacy");
    expect(screen.getByRole("link", { name: /terms/i }).getAttribute("href")).toBe("/terms");
    expect(screen.getByRole("link", { name: /accessibility/i }).getAttribute("href")).toBe("/accessibility");
  });

  it("does not claim to be legal advice", () => {
    render(<Footer />);
    expect(screen.getByText(/not legal advice/i)).toBeTruthy();
  });
});
