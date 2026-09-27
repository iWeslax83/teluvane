# teluvane/teluvane/store.py
import hashlib
import json
import os
from typing import Optional

from psycopg.rows import dict_row

from . import commitments
from .cost import compute_cost
from .db import get_pool
from .schema import Event, Verdict


def _event_canonical_v1(prev_hash: str, e: Event) -> str:
    # The exact string the v1 hash chain digests. org_id is included so an event is
    # cryptographically bound to its tenant. Output bytes are frozen: changing
    # this invalidates every stored v1 chain.
    return json.dumps(
        {
            "prev": prev_hash,
            "org_id": e.org_id,
            "agent_id": e.agent_id,
            "session_id": e.session_id,
            "kind": e.kind,
            "intent": e.intent,
            "tool": e.tool,
            "args": e.args,
            "output": e.output,
            "approved_by": e.approved_by,
            "ts": e.ts,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _event_canonical_v2(prev_hash: str, e: Event) -> str:
    # v2 digests a salted commitment to the personal content instead of the content itself,
    # so the content can be erased later without breaking any hash. Frozen like v1.
    return json.dumps(
        {
            "v": 2,
            "prev": prev_hash,
            "org_id": e.org_id,
            "agent_id": e.agent_id,
            "session_id": e.session_id,
            "kind": e.kind,
            "tool": e.tool,
            "ts": e.ts,
            "payload_commitment": e.payload_commitment,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _event_canonical(prev_hash: str, e: Event) -> str:
    return (_event_canonical_v2 if e.hash_version == 2 else _event_canonical_v1)(prev_hash, e)


def _event_digest(prev_hash: str, e: Event) -> str:
    return hashlib.sha256(_event_canonical(prev_hash, e).encode("utf-8")).hexdigest()


def _write_version() -> int:
    """Hash version for new events. TELUVANE_EVENT_HASH_VERSION=1 is the rollback switch."""
    return 1 if os.environ.get("TELUVANE_EVENT_HASH_VERSION") == "1" else 2


class Store:
    """Tenant-scoped Postgres store. EVERY public method takes org_id as its first argument;
    the _assert_scoped guard makes an un-scoped query impossible by construction."""

    def __init__(self, pool=None):
        self.pool = pool or get_pool()

    # ---- the single audited scoping guard (spec §9.1.1) -------------------------------------
    @staticmethod
    def _assert_scoped(org_id: str, sql: str) -> None:
        if not org_id:
            raise ValueError("org_id is required for every query")
        if "org_id" not in sql.lower():
            raise ValueError(f"refusing un-scoped query (no org_id predicate): {sql!r}")

    # ---- writes -----------------------------------------------------------------------------
    def append(self, org_id: str, e: Event) -> Event:
        sql_last = (
            "SELECT hash FROM events WHERE org_id=%s AND session_id=%s ORDER BY seq DESC LIMIT 1"
        )
        sql_ins = (
            "INSERT INTO events"
            "(org_id,agent_id,session_id,kind,intent,tool,args,output,approved_by,ts,"
            "prev_hash,hash,model,input_tokens,output_tokens,cost_usd,hash_version,"
            "payload_commitment)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING seq"
        )
        sql_payload = "INSERT INTO event_payloads(seq,org_id,salt,payload) VALUES(%s,%s,%s,%s)"
        self._assert_scoped(org_id, sql_last)
        self._assert_scoped(org_id, sql_ins)
        self._assert_scoped(org_id, sql_payload)
        e.org_id = org_id
        # cost_usd isn't part of the hash chain (see _event_digest), so it's safe to fill it
        # in here from a known model's pricing when the caller supplied tokens but no cost.
        if e.cost_usd is None:
            e.cost_usd = compute_cost(e.model, e.input_tokens, e.output_tokens)
        e.hash_version = _write_version()
        salt = payload = None
        if e.hash_version == 2:
            salt = commitments.new_salt()
            payload = commitments.canonical_payload(commitments.payload_of(e))
            e.payload_commitment = commitments.commit(salt, payload)
        # v2 keeps the personal content only in event_payloads; the events row carries blanks.
        if e.hash_version == 2:
            row_intent, row_args, row_output, row_approved = "", {}, "", None
        else:
            row_intent, row_args, row_output, row_approved = (
                e.intent,
                e.args,
                e.output,
                e.approved_by,
            )
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Serialize appends to the same (org, session) for the life of this
                # transaction. Without it two concurrent appends both read the same
                # prev_hash, both digest from it, and the hash chain forks: verify_chain
                # then walks by seq and reports a perfectly legitimate session as
                # TAMPERED. The "append:" prefix keeps this key distinct from the
                # auditlock key for the same session, so an in-flight audit (which can
                # hold its lock across a slow tribunal run) never blocks ingest.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"append:{org_id}:{e.session_id}",),
                )
                cur.execute(sql_last, (org_id, e.session_id))
                row = cur.fetchone()
                e.prev_hash = row["hash"] if row else "GENESIS"
                e.hash = _event_digest(e.prev_hash, e)
                cur.execute(
                    sql_ins,
                    (
                        org_id,
                        e.agent_id,
                        e.session_id,
                        e.kind,
                        row_intent,
                        e.tool,
                        json.dumps(row_args, ensure_ascii=False),
                        row_output,
                        row_approved,
                        e.ts,
                        e.prev_hash,
                        e.hash,
                        e.model,
                        e.input_tokens,
                        e.output_tokens,
                        e.cost_usd,
                        e.hash_version,
                        e.payload_commitment,
                    ),
                )
                e.seq = cur.fetchone()["seq"]
                if e.hash_version == 2:
                    cur.execute(sql_payload, (e.seq, org_id, salt, payload))
            conn.commit()
        return e

    def add_verdict(self, org_id: str, v: Verdict) -> None:
        sql = (
            "INSERT INTO verdicts"
            "(org_id,session_id,rule_id,severity,violation,confidence,evidence_seqs,rationale,framework_ref,ts)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        self._assert_scoped(org_id, sql)
        v.org_id = org_id
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        org_id,
                        v.session_id,
                        v.rule_id,
                        v.severity,
                        v.violation,
                        v.confidence,
                        json.dumps(v.evidence_seqs),
                        v.rationale,
                        v.framework_ref,
                        v.ts,
                    ),
                )
            conn.commit()

    # ---- reads ------------------------------------------------------------------------------
    def _events_with_salt(
        self, org_id: str, session_id: Optional[str] = None
    ) -> list[tuple[Event, Optional[str]]]:
        """Events in seq order, v2 payloads hydrated from event_payloads. The salt is returned
        beside the event (None for v1 or erased events) for commitment checks."""
        sql = (
            "SELECT e.*, p.payload AS _payload, p.salt AS _salt FROM events e "
            "LEFT JOIN event_payloads p ON p.seq = e.seq AND p.org_id = e.org_id "
            "WHERE e.org_id=%s"
        )
        params: tuple = (org_id,)
        if session_id:
            sql += " AND e.session_id=%s"
            params += (session_id,)
        sql += " ORDER BY e.seq ASC"
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        out: list[tuple[Event, Optional[str]]] = []
        for r in rows:
            payload, salt = r.pop("_payload"), r.pop("_salt")
            if r["hash_version"] == 2:
                if payload is None:
                    r["erased"] = True
                else:
                    r.update(json.loads(payload))
            out.append((Event(**r), salt))
        return out

    def events(self, org_id: str, session_id: Optional[str] = None) -> list[Event]:
        return [e for e, _ in self._events_with_salt(org_id, session_id)]

    def verdicts(self, org_id: str, session_id: Optional[str] = None) -> list[Verdict]:
        sql = "SELECT * FROM verdicts WHERE org_id=%s"
        params: tuple = (org_id,)
        if session_id:
            sql += " AND session_id=%s"
            params += (session_id,)
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d.pop("id", None)
            out.append(Verdict(**d))
        return out

    def verify_chain(self, org_id: str, session_id: Optional[str] = None) -> bool:
        """Every event's hash must match its canonical form and link to the previous event in
        its own session. For v2 events whose payload still exists, the payload must also match
        its commitment; without that check editing event_payloads would go unnoticed."""
        prev_by_session: dict[str, str] = {}
        for e, salt in self._events_with_salt(org_id, session_id):
            prev = prev_by_session.get(e.session_id, "GENESIS")
            if _event_digest(prev, e) != e.hash:
                return False
            if e.hash_version == 2 and salt is not None:
                canonical = commitments.canonical_payload(commitments.payload_of(e))
                if commitments.commit(salt, canonical) != e.payload_commitment:
                    return False
            prev_by_session[e.session_id] = e.hash
        return True

    def payload_openings(self, org_id: str, session_id: str) -> list[dict]:
        """Salt and canonical payload for every v2 event whose payload still exists, so an
        auditor can recompute each commitment: sha256(bytes.fromhex(salt) + payload_utf8)."""
        sql = (
            "SELECT p.seq, p.salt, p.payload FROM event_payloads p "
            "JOIN events e ON e.seq = p.seq "
            "WHERE p.org_id=%s AND e.session_id=%s ORDER BY p.seq"
        )
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (org_id, session_id))
            return [dict(r) for r in cur.fetchall()]

    def canonical_events(self, org_id: str, session_id: str) -> list[dict]:
        """Per-event digest inputs for independent (browser) verification. The
        caller hashes `canonical` and checks it equals `hash`, then checks the
        chain links, without trusting this server to have hashed correctly."""
        out = []
        prev = "GENESIS"
        for e in self.events(org_id, session_id):
            out.append(
                {
                    "seq": e.seq,
                    "prev_hash": prev,
                    "hash": e.hash,
                    "canonical": _event_canonical(prev, e),
                }
            )
            prev = e.hash
        return out

    def violation_trend(self, org_id: str, days: int = 30) -> list[dict]:
        """Confirmed-violation counts per UTC day for the last `days` days, oldest first,
        zero-filled so a quiet day still appears (a chart with gaps reads as broken data)."""
        days = max(1, min(days, 365))
        sql = (
            "SELECT d::date AS day, count(v.*) AS violations "
            "FROM generate_series(current_date - (%s - 1) * interval '1 day', current_date, "
            "interval '1 day') AS d "
            "LEFT JOIN verdicts v ON v.org_id=%s AND v.violation AND v.ts::date = d::date "
            "GROUP BY d ORDER BY d"
        )
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (days, org_id))
            rows = cur.fetchall()
        return [{"date": r["day"].isoformat(), "violations": r["violations"]} for r in rows]

    def usage(self, org_id: str, days: int = 30) -> list[dict]:
        """Per-UTC-day token/cost totals for the last `days` days, oldest first, zero-filled.
        Only llm_call events carry token/cost data; rows without it contribute zero."""
        days = max(1, min(days, 365))
        sql = (
            "SELECT d::date AS day, "
            "coalesce(sum(e.input_tokens), 0) AS input_tokens, "
            "coalesce(sum(e.output_tokens), 0) AS output_tokens, "
            "coalesce(sum(e.cost_usd), 0) AS cost_usd "
            "FROM generate_series(current_date - (%s - 1) * interval '1 day', current_date, "
            "interval '1 day') AS d "
            "LEFT JOIN events e ON e.org_id=%s AND e.kind='llm_call' AND e.ts::date = d::date "
            "GROUP BY d ORDER BY d"
        )
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (days, org_id))
            rows = cur.fetchall()
        return [
            {
                "date": r["day"].isoformat(),
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cost_usd": float(r["cost_usd"]),
            }
            for r in rows
        ]

    def sessions(
        self, org_id: str, q: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Paginated, newest-first session summaries: id, event count, latest timestamp.
        `q` filters by a case-insensitive substring match on session_id. Returning exactly
        `limit` rows is the caller's signal that another page may exist (no separate count
        query, to keep the common unpaginated call cheap and the response shape a plain list
        that existing callers already expect)."""
        where = "WHERE org_id=%s"
        params: tuple = (org_id,)
        if q:
            where += " AND session_id ILIKE %s"
            params += (f"%{q}%",)
        sql = (
            f"SELECT session_id, count(*) AS events, max(ts) AS last_ts FROM events {where} "
            "GROUP BY session_id ORDER BY max(seq) DESC LIMIT %s OFFSET %s"
        )
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params + (limit, offset))
            rows = cur.fetchall()
        out = [
            {"session_id": r["session_id"], "events": r["events"], "last_ts": r["last_ts"]}
            for r in rows
        ]
        ids = [r["session_id"] for r in out]
        if ids:
            anchor_status: dict[str, str] = {}
            astmt = (
                "SELECT sa.session_id, b.status FROM session_anchors sa "
                "JOIN anchor_batches b ON b.id = sa.batch_id "
                "WHERE sa.org_id=%s AND sa.session_id = ANY(%s) "
                "ORDER BY sa.anchored_through_seq DESC"
            )
            self._assert_scoped(org_id, astmt)
            with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute(astmt, (org_id, ids))
                for row in cur.fetchall():
                    anchor_status.setdefault(row["session_id"], row["status"])
            for r in out:
                r["anchor"] = anchor_status.get(r["session_id"], "none")
        return out
