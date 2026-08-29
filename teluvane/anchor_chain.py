"""Thin web3.py wrapper for the SessionAnchorRegistry contract. All calls are
synchronous and single-shot; callers handle retries and error isolation."""
import json
import logging

log = logging.getLogger("teluvane.anchor")

ABI = json.loads("""
[
 {"type":"function","name":"anchorBatch","stateMutability":"nonpayable",
  "inputs":[{"name":"root","type":"bytes32"},{"name":"sessionCount","type":"uint256"}],
  "outputs":[]},
 {"type":"function","name":"anchoredAt","stateMutability":"view",
  "inputs":[{"name":"","type":"bytes32"}],"outputs":[{"name":"","type":"uint256"}]},
 {"type":"function","name":"owner","stateMutability":"view",
  "inputs":[],"outputs":[{"name":"","type":"address"}]},
 {"type":"event","name":"BatchAnchored","anonymous":false,
  "inputs":[{"name":"root","type":"bytes32","indexed":true},
            {"name":"sessionCount","type":"uint256","indexed":false},
            {"name":"timestamp","type":"uint256","indexed":false}]}
]
""")


def make_w3(cfg):
    from web3 import Web3
    return Web3(Web3.HTTPProvider(cfg.rpc_url, request_kwargs={"timeout": 15}))


def _account(cfg):
    from eth_account import Account
    return Account.from_key(cfg.signer_key)


def signer_address(cfg) -> str:
    return _account(cfg).address


def _contract(cfg, w3):
    from web3 import Web3
    return w3.eth.contract(address=Web3.to_checksum_address(cfg.contract_address), abi=ABI)


def balance_avax(cfg) -> float:
    w3 = make_w3(cfg)
    wei = w3.eth.get_balance(signer_address(cfg))
    return w3.from_wei(wei, "ether")


def block_number(cfg) -> int:
    return make_w3(cfg).eth.block_number


def read_anchored_at(cfg, root_hex: str) -> int:
    w3 = make_w3(cfg)
    root = bytes.fromhex(root_hex[2:] if root_hex.startswith("0x") else root_hex)
    return int(_contract(cfg, w3).functions.anchoredAt(root).call())


def submit_batch(cfg, root_hex: str, session_count: int) -> str:
    w3 = make_w3(cfg)
    addr = signer_address(cfg)
    root = bytes.fromhex(root_hex[2:] if root_hex.startswith("0x") else root_hex)
    contract = _contract(cfg, w3)
    nonce = w3.eth.get_transaction_count(addr, "pending")
    max_priority = w3.to_wei(2, "gwei")
    base = w3.eth.gas_price
    tx = contract.functions.anchorBatch(root, session_count).build_transaction({
        "from": addr,
        "nonce": nonce,
        "chainId": cfg.chain_id,
        "gas": 120000,
        "maxPriorityFeePerGas": max_priority,
        "maxFeePerGas": base * 2 + max_priority,
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=cfg.signer_key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    return "0x" + txh.hex() if not txh.hex().startswith("0x") else txh.hex()


def receipt(cfg, tx_hash: str):
    w3 = make_w3(cfg)
    try:
        r = w3.eth.get_transaction_receipt(tx_hash)
    except Exception:
        return None
    if r is None:
        return None
    return {
        "block_number": int(r["blockNumber"]),
        "status": int(r["status"]),
        "gas_used": int(r["gasUsed"]),
        "effective_gas_price": int(r.get("effectiveGasPrice", 0)),
    }
