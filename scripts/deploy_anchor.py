"""Compile and deploy SessionAnchorRegistry to the chain in ANCHOR_RPC_URL,
signed by ANCHOR_SIGNER_PRIVATE_KEY. Prints the deployed address.

  python scripts/deploy_anchor.py

Env:
  ANCHOR_RPC_URL             (required) JSON-RPC endpoint, e.g. an Avalanche Fuji node
  ANCHOR_SIGNER_PRIVATE_KEY  (required) hot-wallet key, 0x-prefixed or bare hex
  ANCHOR_CHAIN_ID            (optional) defaults to 43113 (Fuji C-Chain)

This is operator tooling. It sends a real transaction and spends gas, so it is
never run in CI. The deployer address becomes the contract owner (the only
account allowed to call anchorBatch), so deploy with the same key you will set
as ANCHOR_SIGNER_PRIVATE_KEY on the backend.
"""

import os
import sys
from pathlib import Path

from eth_account import Account
from solcx import compile_standard, install_solc
from web3 import Web3

SOL = Path("contracts/SessionAnchorRegistry.sol")
SOLC_VERSION = "0.8.24"


def main() -> int:
    rpc = os.environ["ANCHOR_RPC_URL"]
    key = os.environ["ANCHOR_SIGNER_PRIVATE_KEY"]
    chain_id = int(os.environ.get("ANCHOR_CHAIN_ID", "43113"))

    if not SOL.exists():
        print("contract not found:", SOL, "(run from the repo root)", file=sys.stderr)
        return 1

    install_solc(SOLC_VERSION)
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {SOL.name: {"content": SOL.read_text()}},
            "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}},
        },
        solc_version=SOLC_VERSION,
    )
    c = compiled["contracts"][SOL.name]["SessionAnchorRegistry"]
    abi, bytecode = c["abi"], c["evm"]["bytecode"]["object"]

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    acct = Account.from_key(key)
    print("deployer:", acct.address)
    print("balance:", w3.from_wei(w3.eth.get_balance(acct.address), "ether"), "AVAX")

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    max_priority = w3.to_wei(2, "gwei")
    tx = contract.constructor().build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 500000,
            "maxPriorityFeePerGas": max_priority,
            "maxFeePerGas": w3.eth.gas_price * 2 + max_priority,
            "chainId": chain_id,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, private_key=key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("deploy tx:", txh.hex())
    rcpt = w3.eth.wait_for_transaction_receipt(txh)
    if rcpt["status"] != 1:
        print("deploy reverted:", dict(rcpt), file=sys.stderr)
        return 1
    print("ANCHOR_CONTRACT_ADDRESS=" + rcpt["contractAddress"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
