import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import EvidenceLogCard from "./EvidenceLogCard";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" } }),
  IBM_Plex_Mono: () => ({ className: "", style: { fontFamily: "IBM Plex Mono" } }),
}));

describe("EvidenceLogCard", () => {
  it("renders the demo chain as intact", () => {
    render(<EvidenceLogCard />);
    expect(screen.getByText("INTACT")).toBeTruthy();
    expect(screen.getAllByText(/send_email/).length).toBeGreaterThan(0);
  });

  it("editing an event breaks the chain at that event, restoring repairs it", async () => {
    render(<EvidenceLogCard />);
    fireEvent.click(screen.getByRole("button", { name: /edit event #3/i }));
    expect(await screen.findByText("BROKEN at #3")).toBeTruthy();
    expect(screen.getByText("MISMATCH")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /restore event #3/i }));
    expect(await screen.findByText("INTACT")).toBeTruthy();
  });

  it("editing an early event leaves later events unverified", async () => {
    render(<EvidenceLogCard />);
    fireEvent.click(screen.getByRole("button", { name: /edit event #1/i }));
    expect(await screen.findByText("BROKEN at #1")).toBeTruthy();
    expect(screen.getAllByText("unverified")).toHaveLength(2);
  });
});
