# teluvane/tests/test_evidence.py
from teluvane.evidence import build_evidence_pack, build_evidence_pdf
from teluvane.schema import Event, Verdict

def _sample():
    events = [Event(agent_id="d", session_id="s1", kind="tool_call", tool="send_email",
                    args={"to": "evil@x.com"}, intent="exfiltrate", seq=1, hash="abc")]
    verdicts = [Verdict(session_id="s1", rule_id="data_exfiltration", severity="critical",
                        violation=True, confidence=0.92, evidence_seqs=[1],
                        rationale="emailed DB to external", framework_ref="Art.12")]
    return events, verdicts

def test_build_evidence_pack_html_and_json():
    events, verdicts = _sample()
    pack = build_evidence_pack("s1", events, verdicts, framework="EU AI Act",
                               chain_intact=True)
    assert pack["json"]["session_id"] == "s1"
    assert pack["json"]["summary"]["violations"] == 1
    assert "data_exfiltration" in pack["html"]
    assert "EU AI Act" in pack["html"] and "Art.12" in pack["html"]

def test_build_evidence_pdf_is_a_real_pdf():
    events, verdicts = _sample()
    pdf = build_evidence_pdf("s1", events, verdicts, framework="EU AI Act", chain_intact=True)
    assert pdf.startswith(b"%PDF-")

def test_evidence_pack_without_anchor_says_not_anchored():
    pack = build_evidence_pack("s1", [], [], "eu_ai_act", True, anchor=None)
    assert "not anchored" in pack["html"].lower()

def test_evidence_pack_with_anchor_shows_tx_and_privacy_line():
    a = {"anchored": True, "status": "verified", "root": "0xabc", "tx_hash": "0xdef",
         "block_number": 42, "through_seq": 3, "total_seq": 3, "onchain_ts": 1700000000,
         "explorer_tx_url": "https://testnet.snowtrace.io/tx/"}
    pack = build_evidence_pack("s1", [], [], "eu_ai_act", True, anchor=a)
    html = pack["html"]
    assert "https://testnet.snowtrace.io/tx/0xdef" in html
    assert "0xabc" in html
    assert "only hashes" in html.lower()
    assert pack["json"]["anchor"]["tx_hash"] == "0xdef"

def test_evidence_pack_embeds_canonical_when_given():
    events, verdicts = _sample()
    canon = [{"seq": 1, "prev_hash": None, "hash": "abc",
              "canonical": '{"prev": null, "kind": "tool_call"}'}]
    pack = build_evidence_pack("s1", events, verdicts, framework="EU AI Act",
                               chain_intact=True, canonical=canon)
    assert pack["json"]["canonical"] == canon

def test_evidence_pack_canonical_defaults_to_none():
    events, verdicts = _sample()
    pack = build_evidence_pack("s1", events, verdicts, framework="EU AI Act",
                               chain_intact=True)
    assert pack["json"]["canonical"] is None
