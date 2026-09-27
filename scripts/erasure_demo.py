"""Live demo of GDPR erasure on a hash-chained log. Needs DATABASE_URL (a throwaway database).

    python scripts/erasure_demo.py

Records a session containing personal data, verifies the chain, erases the personal content,
and shows the chain still verifies with identical hashes. Everything is cleaned up at the end.
"""

import secrets

from teluvane.db import get_pool
from teluvane.migrate import apply_migrations
from teluvane.schema import Event
from teluvane.store import Store


def main() -> None:
    apply_migrations()
    store = Store()
    org = "demo-" + secrets.token_hex(4)
    session = "erasure-demo"
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES(%s,'demo','demo')", (org,))
        conn.commit()
    try:
        for intent, args in [
            ("look up the customer", {"name": "Jane Doe", "email": "jane@example.com"}),
            ("record their national id", {"ssn": "078-05-1120"}),
            ("send confirmation", {"to": "jane@example.com", "body": "Your request is done."}),
        ]:
            store.append(
                org,
                Event(
                    agent_id="demo",
                    session_id=session,
                    kind="tool_call",
                    tool="crm",
                    intent=intent,
                    args=args,
                    approved_by="human:demo",
                ),
            )
        heads_before = [r["hash"] for r in store.canonical_events(org, session)]
        print("1. recorded 3 events with personal data")
        print("   chain:", store.verify_report(org, session))
        print("   event 2 args:", store.events(org, session)[1].args)

        result = store.erase_payloads(org, session, requested_by="demo", reason="art 17 request")
        print("\n2. erased on request:", result)

        events = store.events(org, session)
        print("   event 2 args:", events[1].args, "| erased:", events[1].erased)
        print("   chain:", store.verify_report(org, session))
        same = heads_before == [r["hash"] for r in store.canonical_events(org, session)]
        print("   every hash identical to before erasure:", same)
    finally:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM erasure_log WHERE org_id=%s", (org,))
            cur.execute("DELETE FROM events WHERE org_id=%s", (org,))
            cur.execute("DELETE FROM orgs WHERE id=%s", (org,))
            conn.commit()


if __name__ == "__main__":
    main()
