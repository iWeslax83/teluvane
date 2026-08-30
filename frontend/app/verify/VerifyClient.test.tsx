import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import VerifyClient from "./VerifyClient";

// Mutable stand-in for the build-time pins so a single test can drop the pin.
const cfg = vi.hoisted(() => ({
  contract: undefined as string | undefined,
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
  cfg.contract = undefined;
  cfg.rpc = undefined;
});

function serve(bundle: unknown) {
  globalThis.fetch = vi.fn(async () => ({
    ok: true,
    json: async () => bundle,
  })) as unknown as typeof fetch;
}

function verifySessionId(id: string) {
  fireEvent.change(screen.getByLabelText(/session id/i), { target: { value: id } });
  fireEvent.click(screen.getAllByRole("button", { name: /verify/i })[0]);
}

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

  it("reads the pinned contract address, not the one the API bundle reports", async () => {
    cfg.contract = "0xPINNED";
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    serve({ ...publicBundle, contract_address: "0xEVIL", rpc_url: "http://evil.example/rpc" });

    render(<VerifyClient />);
    verifySessionId("s1");

    expect(await screen.findByText(/verified/i)).toBeTruthy();
    expect(mockReadContract).toHaveBeenCalledTimes(1);
    expect(mockReadContract.mock.calls[0][0].address).toBe("0xPINNED");
  });

  it("does not verify when the API bundle reports a different chain id", async () => {
    cfg.contract = "0xPINNED";
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    serve({ ...publicBundle, chain_id: 1 });

    render(<VerifyClient />);
    verifySessionId("s1");

    expect(await screen.findByText(/could not reach an Avalanche RPC/i)).toBeTruthy();
    expect(mockReadContract).not.toHaveBeenCalled();
  });

  it("says it could not independently verify when nothing pins the contract", async () => {
    serve({ ...publicBundle, contract_address: undefined });

    render(<VerifyClient />);
    verifySessionId("s1");

    expect(await screen.findByText(/no pinned contract/i)).toBeTruthy();
    expect(mockReadContract).not.toHaveBeenCalled();
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

  it("ignores hostile network/explorer fields in a pasted evidence pack", async () => {
    cfg.contract = "0xPINNED";
    mockReadContract.mockResolvedValue(BigInt(1_700_000_000));
    const hostilePack = JSON.stringify({
      session_id: "s1",
      canonical: [
        { seq: 1, prev_hash: "GENESIS", hash: "h1", canonical: JSON.stringify({ prev: "GENESIS" }) },
      ],
      proof: [],
      root: "0xroot",
      chain_head: "h1",
      tx_hash: "0xtx",
      contract_address: "0xEVIL",
      rpc_url: "http://evil.example/rpc",
      explorer_tx_url: "javascript:alert(1)",
      anchor: { org_id: "org1", status: "verified", head_stored: "h1", head_matches: true },
    });
    const { container } = render(<VerifyClient />);
    fireEvent.change(screen.getByLabelText(/evidence pack json/i), { target: { value: hostilePack } });
    fireEvent.click(screen.getAllByRole("button", { name: /verify/i })[1]);

    // Wait for the rendered result region (not the textarea echo of the input).
    await screen.findByText(/result from the evidence pack/i);
    const region = container.querySelector('[aria-live="polite"]') as HTMLElement;
    const links = Array.from(region.querySelectorAll("a"));
    // No hostile scheme reaches an href, and the attacker's contract/RPC/explorer
    // values from the pasted pack never appear in the rendered result.
    expect(links.every((a) => (a.getAttribute("href") ?? "").startsWith("https://"))).toBe(true);
    expect(region.innerHTML).not.toContain("javascript:alert(1)");
    expect(region.innerHTML).not.toContain("0xEVIL");
    expect(region.innerHTML).not.toContain("evil.example");
    expect(mockReadContract.mock.calls[0][0].address).toBe("0xPINNED");
  });
});
