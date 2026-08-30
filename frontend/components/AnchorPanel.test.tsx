import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import AnchorPanel from "./AnchorPanel";

const mockReadContract = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (path: string) => {
    if (path.endsWith("/canonical")) {
      return [{ seq: 1, prev_hash: "GENESIS", hash: "h1", canonical: '{"prev":"GENESIS"}' }];
    }
    if (path === "/anchor/contract") {
      return {
        chain_id: 43113,
        contract_address: "0xC0",
        explorer_tx_url: "https://x/tx/",
        rpc_url: "http://rpc",
      };
    }
    if (path.startsWith("/anchor/")) {
      return {
        anchored: true,
        org_id: "o1",
        proof: ["0xsib"],
        status: "verified",
        through_seq: 1,
        total_seq: 1,
        root: "0xroot",
        tx_hash: "0xtx",
        block_number: 9,
        head_stored: "h1",
        head_recomputed: "h1",
        head_matches: true,
        proof_ok: true,
      };
    }
    return {};
  }),
}));

vi.mock("@/lib/merkle", () => ({ rootFromProof: vi.fn(async () => "0xroot") }));
vi.mock("@/lib/chainVerify", () => ({ verifyChain: vi.fn(async () => ({ ok: true, head: "h1" })) }));
vi.mock("viem", () => ({
  createPublicClient: () => ({ readContract: mockReadContract }),
  http: () => ({}),
}));
vi.mock("viem/chains", () => ({ avalancheFuji: { id: 43113 } }));

beforeEach(() => {
  mockReadContract.mockReset();
});

describe("AnchorPanel", () => {
  it("shows the verified state with a snowtrace link when local and on-chain agree", async () => {
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    const link = await screen.findByRole("link", { name: /0xtx/i });
    expect(link.getAttribute("href")).toBe("https://x/tx/0xtx");
    expect(screen.getByText(/recorded on Avalanche/i)).toBeTruthy();
    expect(screen.getByText(/block 9/i)).toBeTruthy();
    // The server's own verdict is shown, secondary.
    expect(screen.getByText(/TELUVANE's check/i)).toBeTruthy();
  });

  it("shows a mismatch when the root is absent on-chain", async () => {
    mockReadContract.mockResolvedValue(BigInt(0));
    render(<AnchorPanel token="t" sessionId="s2" />);

    expect(await screen.findByText(/does not match|not found on Avalanche/i)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /0xtx/i })).toBeNull();
  });

  it("shows rpc-unreachable when the contract read throws", async () => {
    mockReadContract.mockRejectedValue(new Error("boom"));
    render(<AnchorPanel token="t" sessionId="s3" />);

    expect(await screen.findByText(/could not reach|rpc/i)).toBeTruthy();
  });
});
