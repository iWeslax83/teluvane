import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AnchorResult from "./AnchorResult";

describe("AnchorResult", () => {
  it("links the tx hash when the explorer URL is https", () => {
    render(
      <AnchorResult
        state={{ kind: "verified" }}
        onchainTs={1_700_000_000}
        block={9}
        tx="0xtx"
        txUrl="https://testnet.snowtrace.io/tx/0xtx"
      />,
    );
    const link = screen.getByRole("link", { name: /0xtx/i });
    expect(link.getAttribute("href")).toBe("https://testnet.snowtrace.io/tx/0xtx");
  });

  it("never renders a non-https href, shows the tx as plain text instead", () => {
    const { container } = render(
      <AnchorResult
        state={{ kind: "verified" }}
        onchainTs={1_700_000_000}
        block={9}
        tx="0xtx"
        txUrl="javascript:alert(1)"
      />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(/0xtx/)).toBeTruthy();
  });

  it("renders plain text when there is no explorer URL at all", () => {
    const { container } = render(
      <AnchorResult state={{ kind: "verified" }} onchainTs={1_700_000_000} tx="0xtx" />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(screen.getByText(/0xtx/)).toBeTruthy();
  });
});
