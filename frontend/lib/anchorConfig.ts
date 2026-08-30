// Build-time pins for the browser's on-chain read.
//
// The whole point of the anchor check is that the browser talks to Avalanche
// itself. If the contract address or the RPC endpoint came from the TELUVANE
// API, a compromised server could serve a self-consistent fake session plus a
// contract it controls that answers "yes, anchored", and the page would print
// "Verified". So these are inlined at build time by Next and are never read
// from an API response or a pasted evidence pack.
//
// NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS is what makes the check independent. When
// it is blank the page falls back to the address the API reports and says so
// (the "unpinned" state), rather than claiming an independent verification.

export const ANCHOR_CONTRACT = process.env.NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS || undefined;

// Blank is fine: viem then uses avalancheFuji's own public endpoint. The
// API-supplied rpc_url is never used.
export const ANCHOR_RPC = process.env.NEXT_PUBLIC_ANCHOR_RPC_URL || undefined;

export const EXPLORER =
  process.env.NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL || "https://testnet.snowtrace.io/tx/";
