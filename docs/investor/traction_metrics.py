#!/usr/bin/env python3
"""Pull real traction numbers for investor/pilot collateral.

Run against the PRODUCTION database, not local dev sqlite:

    export DATABASE_URL=postgresql://...  # prod Supabase connection string
    python docs/investor/traction_metrics.py
"""
import os
import sys

import psycopg


QUERIES = {
    "orgs_total": "SELECT count(*) FROM orgs",
    "orgs_paid": "SELECT count(*) FROM orgs WHERE plan != 'free' AND plan_status = 'active'",
    "orgs_created_last_30d": "SELECT count(*) FROM orgs WHERE created_at > now() - interval '30 days'",
    "sessions_total": "SELECT count(DISTINCT (org_id, session_id)) FROM events",
    "events_total": "SELECT count(*) FROM events",
    "events_last_30d": "SELECT count(*) FROM events WHERE ts::timestamptz > now() - interval '30 days'",
    "audits_run_total": "SELECT count(DISTINCT (org_id, session_id)) FROM verdicts",
    "violations_found_total": "SELECT count(*) FROM verdicts WHERE violation = true",
    "billing_events_total": "SELECT count(*) FROM billing_events",
}


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL to the production connection string first.", file=sys.stderr)
        return 1

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            print("TELUVANE traction metrics")
            print("=" * 40)
            for label, sql in QUERIES.items():
                try:
                    cur.execute(sql)
                    value = cur.fetchone()[0]
                except Exception as exc:  # noqa: BLE001 - report and keep going
                    value = f"ERROR: {exc}"
                    conn.rollback()
                print(f"{label:28s} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
