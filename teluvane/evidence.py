# teluvane/teluvane/evidence.py
import html as _html
from .schema import Event, Verdict

def build_evidence_pack(session_id: str, events: list[Event], verdicts: list[Verdict],
                        framework: str, chain_intact: bool,
                        anchor: dict | None = None,
                        canonical: list[dict] | None = None) -> dict:
    violations = [v for v in verdicts if v.violation]
    summary = {"events": len(events), "violations": len(violations),
               "chain_intact": chain_intact,
               "highest_severity": _highest_sev(violations)}
    js = {"session_id": session_id, "framework": framework, "summary": summary,
          "anchor": anchor,
          "canonical": canonical,
          "violations": [v.model_dump() for v in violations],
          "events": [e.model_dump() for e in events]}
    return {"json": js, "html": _render_html(session_id, framework, summary,
                                             violations, events, anchor)}

def build_evidence_pdf(session_id: str, events: list[Event], verdicts: list[Verdict],
                       framework: str, chain_intact: bool,
                       anchor: dict | None = None,
                       canonical: list[dict] | None = None) -> bytes:
    # Imported lazily: weasyprint pulls in cairo/pango bindings that only the PDF export
    # path needs, so the rest of the API can boot even if that native stack is unavailable.
    from weasyprint import HTML
    pack = build_evidence_pack(session_id, events, verdicts, framework, chain_intact,
                               anchor, canonical)
    return HTML(string=pack["html"]).write_pdf()

_SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

def _highest_sev(vs: list[Verdict]) -> str:
    return max((v.severity for v in vs), key=lambda s: _SEV_ORDER.get(s, -1), default="none")

def _render_anchor_html(anchor: dict | None) -> str:
    if not anchor or not anchor.get("anchored"):
        return ("<h2>On-chain anchor</h2><p>This session is not anchored on "
                "Avalanche. The SHA-256 event chain above is still tamper-evident "
                "within TELUVANE.</p>")
    tx = anchor.get("tx_hash") or ""
    url = (anchor.get("explorer_tx_url") or "") + tx
    return (
        "<h2>On-chain anchor</h2><p>"
        f"<b>Status:</b> {_html.escape(str(anchor.get('status', '')))}<br>"
        f"<b>Merkle root:</b> <code>{_html.escape(str(anchor.get('root', '')))}</code><br>"
        f"<b>Avalanche Fuji tx:</b> "
        f"<a href=\"{_html.escape(url)}\">{_html.escape(tx)}</a><br>"
        f"<b>Block:</b> {_html.escape(str(anchor.get('block_number')))}<br>"
        f"<b>Anchored through event:</b> {_html.escape(str(anchor.get('through_seq')))} "
        f"of {_html.escape(str(anchor.get('total_seq')))}</p>"
        "<p><b>Chain of custody:</b> SHA-256 event chain (through event "
        f"{_html.escape(str(anchor.get('through_seq')))} of "
        f"{_html.escape(str(anchor.get('total_seq')))}) to Merkle root to "
        f"Avalanche Fuji tx {_html.escape(tx)} at block "
        f"{_html.escape(str(anchor.get('block_number')))}.</p>"
        "<p><b>Privacy:</b> Only hashes and a batch count are written on chain. "
        "No event content, tool arguments, model output, or personal data leaves TELUVANE.</p>")

def _render_html(session_id, framework, summary, violations, events, anchor=None) -> str:
    rows = "".join(
        f"<tr><td>{_html.escape(v.rule_id)}</td><td>{v.severity}</td>"
        f"<td>{v.confidence:.2f}</td><td>{_html.escape(str(v.evidence_seqs))}</td>"
        f"<td>{_html.escape(v.framework_ref)}</td><td>{_html.escape(v.rationale)}</td></tr>"
        for v in violations)
    ev_rows = "".join(
        f"<tr><td>#{e.seq}</td><td>{e.kind}</td><td>{_html.escape(e.tool or '')}</td>"
        f"<td>{_html.escape(e.intent)}</td><td><code>{_html.escape(str(e.args))}</code></td></tr>"
        for e in events)
    chain = "&#9989; intact" if summary["chain_intact"] else "&#10060; TAMPERED"
    anchor_html = _render_anchor_html(anchor)
    return f"""<!doctype html><meta charset=utf-8>
<title>Evidence Pack — {_html.escape(session_id)}</title>
<style>body{{font-family:system-ui;margin:2rem;color:#1a1714}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:6px;text-align:left;font-size:14px}}
h1{{color:#b4451f}}.sev-critical{{color:#b4451f;font-weight:700}}</style>
<h1>Compliance Evidence Pack</h1>
<p><b>Framework:</b> {_html.escape(framework)} &nbsp;|&nbsp;
<b>Session:</b> {_html.escape(session_id)} &nbsp;|&nbsp;
<b>Tamper-evidence chain:</b> {chain}</p>
<p><b>Events:</b> {summary['events']} &nbsp;|&nbsp;
<b>Violations:</b> {summary['violations']} &nbsp;|&nbsp;
<b>Highest severity:</b> {summary['highest_severity']}</p>
{anchor_html}
<h2>Violations</h2><table><tr><th>Rule</th><th>Severity</th><th>Confidence</th>
<th>Evidence</th><th>Framework ref</th><th>Rationale</th></tr>{rows}</table>
<h2>Full Action Log</h2><table><tr><th>#</th><th>Kind</th><th>Tool</th>
<th>Intent</th><th>Args</th></tr>{ev_rows}</table>"""
