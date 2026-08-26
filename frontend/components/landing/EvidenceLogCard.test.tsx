import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import EvidenceLogCard from "./EvidenceLogCard";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" } }),
  IBM_Plex_Mono: () => ({ className: "", style: { fontFamily: "IBM Plex Mono" } }),
}));

describe("EvidenceLogCard", () => {
  it("renders the hash-chained event log with an intact chain", () => {
    render(<EvidenceLogCard />);
    expect(screen.getByText(/agent_log\.chain/i)).toBeTruthy();
    expect(screen.getByText("INTACT")).toBeTruthy();
    expect(screen.getByText("send_email")).toBeTruthy();
  });
});
