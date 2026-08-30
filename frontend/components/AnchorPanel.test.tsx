import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AnchorPanel from "./AnchorPanel";

const mockReadContract = vi.fn();

// Mutable stand-in for the build-time pins so a single test can drop the pin.
const cfg = vi.hoisted(() => ({
  contract: "0xPINNED" as string | undefined,
  rpc: undefined as string | undefined,
}));
vi.mock("@/lib/anchorConfig", () => ({
  get ANCHOR_CONTRACT() {
    return cfg.contract;
  },
  get ANCHOR_RPC() {
    return cfg.rpc;
  },
  EXPLORER: "https://testnet.snowtrace.io/tx/",
}));

// The API deliberately reports a DIFFERENT contract address and its own RPC.
// Neither may reach the on-chain read while a build-time pin exists.
const api = vi.hoisted(() => ({ chainId: 43113, contractAddress: "0xC0" as string | undefined }));
const putCalls = vi.hoisted(() => [] as unknown[]);

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (path: string, opts?: { method?: string; body?: unknown }) => {
    if (path.endsWith("/public") && opts?.method === "PUT") {
      putCalls.push(opts.body);
      return { public: true };
    }
    if (path.endsWith("/canonical")) {
      return [{ seq: 1, prev_hash: "GENESIS", hash: "h1", canonical: '{"prev":"GENESIS"}' }];
    }
    if (path === "/anchor/contract") {
      return {
        chain_id: api.chainId,
        contract_address: api.contractAddress,
        explorer_tx_url: "https://x/tx/",
        rpc_url: "http://evil.example/rpc",
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
        is_public: false,
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
  cfg.contract = "0xPINNED";
  cfg.rpc = undefined;
  api.chainId = 43113;
  api.contractAddress = "0xC0";
  putCalls.length = 0;
});

describe("AnchorPanel", () => {
  it("shows the verified state with a snowtrace link when local and on-chain agree", async () => {
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    const link = await screen.findByRole("link", { name: /0xtx/i });
    // Built from the pinned EXPLORER constant, not the API's explorer_tx_url.
    expect(link.getAttribute("href")).toBe("https://testnet.snowtrace.io/tx/0xtx");
    expect(screen.getByText(/recorded on Avalanche/i)).toBeTruthy();
    expect(screen.getByText(/block 9/i)).toBeTruthy();
    // The server's own verdict is shown, secondary.
    expect(screen.getByText(/TELUVANE's check/i)).toBeTruthy();
  });

  it("reads the pinned contract address, not the one the API reports", async () => {
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    await screen.findByText(/recorded on Avalanche/i);
    expect(mockReadContract).toHaveBeenCalledTimes(1);
    expect(mockReadContract.mock.calls[0][0].address).toBe("0xPINNED");
  });

  it("does not verify when the API reports a different chain id", async () => {
    api.chainId = 1;
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    expect(await screen.findByText(/could not reach an Avalanche RPC/i)).toBeTruthy();
    expect(mockReadContract).not.toHaveBeenCalled();
    expect(screen.queryByText(/recorded on Avalanche/i)).toBeNull();
  });

  it("says it could not independently verify when nothing pins the contract, even though the API serves a valid-looking one", async () => {
    cfg.contract = undefined;
    // The API still reports a real-looking contract on the right chain, and the
    // contract would answer with a non-zero anchoredAt. None of it may be used.
    api.chainId = 43113;
    api.contractAddress = "0xC0";
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    expect(await screen.findByText(/no pinned contract/i)).toBeTruthy();
    expect(mockReadContract).not.toHaveBeenCalled();
    expect(screen.queryByText(/Independent check, read from Avalanche/i)).toBeNull();
    expect(screen.queryByText(/recorded on Avalanche/i)).toBeNull();
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

  it("publishes the session for public verification from the checkbox", async () => {
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    render(<AnchorPanel token="t" sessionId="s1" />);

    const box = (await screen.findByLabelText(/publish this session/i)) as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);

    await waitFor(() => expect(putCalls).toEqual([{ public: true }]));
    expect(box.checked).toBe(true);
  });
});
