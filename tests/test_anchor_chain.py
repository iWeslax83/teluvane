from unittest.mock import MagicMock, patch
from teluvane import anchor_chain
from teluvane.anchor import AnchorConfig

CFG = AnchorConfig(rpc_url="http://rpc", contract_address="0x00000000000000000000000000000000000000aa",
                   signer_key="0x" + "11" * 32)


def _fake_w3():
    w3 = MagicMock()
    w3.eth.get_transaction_count.return_value = 7
    w3.eth.chain_id = 43113
    w3.eth.gas_price = 25_000_000_000
    w3.eth.block_number = 500
    w3.to_wei = lambda v, u: int(v * 1e9)
    w3.from_wei = lambda v, u: v / 1e18
    return w3


def test_submit_batch_signs_and_sends():
    w3 = _fake_w3()
    contract = MagicMock()
    tx = {"from": "0xSigner", "nonce": 7}
    contract.functions.anchorBatch.return_value.build_transaction.return_value = tx
    w3.eth.contract.return_value = contract
    signed = MagicMock(raw_transaction=b"raw")
    w3.eth.account.sign_transaction.return_value = signed
    w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)

    with patch.object(anchor_chain, "make_w3", return_value=w3), \
         patch.object(anchor_chain, "signer_address", return_value="0xSigner"):
        txh = anchor_chain.submit_batch(CFG, "0x" + "cd" * 32, 3)
    assert txh == "0x" + "ab" * 32
    contract.functions.anchorBatch.assert_called_once()
    args = contract.functions.anchorBatch.call_args[0]
    assert args[1] == 3


def test_read_anchored_at_returns_zero_when_unanchored():
    w3 = _fake_w3()
    contract = MagicMock()
    contract.functions.anchoredAt.return_value.call.return_value = 0
    w3.eth.contract.return_value = contract
    with patch.object(anchor_chain, "make_w3", return_value=w3):
        assert anchor_chain.read_anchored_at(CFG, "0x" + "00" * 32) == 0


def test_receipt_none_when_not_mined():
    w3 = _fake_w3()
    w3.eth.get_transaction_receipt.side_effect = Exception("not found")
    with patch.object(anchor_chain, "make_w3", return_value=w3):
        assert anchor_chain.receipt(CFG, "0xabc") is None
