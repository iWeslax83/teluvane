import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import VerifyClient from "./VerifyClient";

vi.mock("@/lib/merkle", () => ({ rootFromProof: vi.fn(async () => "0xroot") }));
vi.mock("@/lib/chainVerify", () => ({
  verifyChain: vi.fn(async () => ({ ok: true, head: "h1" })),
}));

const mockReadContract = vi.fn();
vi.mock("viem", () => ({
  createPublicClient: () => ({ readContract: mockReadContract }),
  http: () => ({}),
}));
vi.mock("viem/chains", () => ({ avalancheFuji: { id: 43113 } }));

const publicBundle = {
  session_id: "s1",
  canonical: [
    { seq: 1, prev_hash: "GENESIS", hash: "h1", canonical: JSON.stringify({ prev: "GENESIS" }) },
  ],
  proof: [],
  chain_head: "h1",
  root: "0xroot",
  tx_hash: "0xtx",
  chain_id: 43113,
  contract_address: "0xC0",
  explorer_tx_url: "https://x/tx/",
  rpc_url: "http://rpc",
  verify: { org_id: "org1", status: "verified", head_stored: "h1", head_matches: true, block_number: 9 },
};

beforeEach(() => {
  mockReadContract.mockReset();
});

describe("VerifyClient", () => {
  it("verifies a public session id and links the anchor transaction", async () => {
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => publicBundle,
    })) as unknown as typeof fetch;

    render(<VerifyClient />);
    fireEvent.change(screen.getByLabelText(/session id/i), { target: { value: "s1" } });
    fireEvent.click(screen.getAllByRole("button", { name: /verify/i })[0]);

    expect(await screen.findByText(/verified/i)).toBeTruthy();
    const link = await screen.findByRole("link", { name: /0xtx/i });
    expect(link.getAttribute("href")).toBe("https://x/tx/0xtx");
  });

  it("shows a no-record message when the public endpoint 404s", async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ detail: "not found" }),
    })) as unknown as typeof fetch;

    render(<VerifyClient />);
    fireEvent.change(screen.getByLabelText(/session id/i), { target: { value: "nope" } });
    fireEvent.click(screen.getAllByRole("button", { name: /verify/i })[0]);

    expect(await screen.findByText(/no public record for this session id/i)).toBeTruthy();
  });

  it("rejects an evidence pack exported before on-chain anchoring", async () => {
    render(<VerifyClient />);
    const pack = JSON.stringify({ session_id: "s1", anchor: { org_id: "org1" }, events: [] });
    fireEvent.change(screen.getByLabelText(/evidence pack json/i), { target: { value: pack } });
    fireEvent.click(screen.getAllByRole("button", { name: /verify/i })[1]);

    expect(await screen.findByText(/re-export to verify offline/i)).toBeTruthy();
  });
});
