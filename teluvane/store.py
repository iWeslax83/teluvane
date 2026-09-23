# teluvane/teluvane/store.py
import hashlib
import json
from typing import Optional

from psycopg.rows import dict_row

from .cost import compute_cost
from .db import get_pool
from .schema import Event, Verdict


def _event_canonical(prev_hash: str, e: Event) -> str:
    # The exact string the hash chain digests. org_id is included so an event is
    # cryptographically bound to its tenant. Output bytes are frozen: changing
    # this invalidates every stored chain.
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


def _event_digest(prev_hash: str, e: Event) -> str:
    return hashlib.sha256(_event_canonical(prev_hash, e).encode("utf-8")).hexdigest()


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
            "prev_hash,hash,model,input_tokens,output_tokens,cost_usd)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING seq"
        )
        self._assert_scoped(org_id, sql_last)
        self._assert_scoped(org_id, sql_ins)
        e.org_id = org_id
        # cost_usd isn't part of the hash chain (see _event_digest), so it's safe to fill it
        # in here from a known model's pricing when the caller supplied tokens but no cost.
        if e.cost_usd is None:
            e.cost_usd = compute_cost(e.model, e.input_tokens, e.output_tokens)
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
                        e.intent,
                        e.tool,
                        json.dumps(e.args, ensure_ascii=False),
                        e.output,
                        e.approved_by,
                        e.ts,
                        e.prev_hash,
                        e.hash,
                        e.model,
                        e.input_tokens,
                        e.output_tokens,
                        e.cost_usd,
                    ),
                )
                e.seq = cur.fetchone()["seq"]
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
    def events(self, org_id: str, session_id: Optional[str] = None) -> list[Event]:
        sql = "SELECT * FROM events WHERE org_id=%s"
        params: tuple = (org_id,)
        if session_id:
            sql += " AND session_id=%s"
            params += (session_id,)
        sql += " ORDER BY seq ASC"
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [Event(**r) for r in rows]

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
        prev = "GENESIS"
        for e in self.events(org_id, session_id):
            if _event_digest(prev, e) != e.hash:
                return False
            prev = e.hash
        return True

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
