import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
import uuid

from teluvane.db import get_pool
from teluvane.orgs import (
    accept_invite,
    create_invite,
    create_org,
    find_pending_invite,
    list_invites,
    list_members,
    org_for_user,
    remove_member,
    revoke_invite,
    set_member_role,
)


def _seed_auth_user(user_id: str, email: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users(id, email) VALUES(%s, %s) "
            "ON CONFLICT (id) DO UPDATE SET email=EXCLUDED.email",
            (user_id, email),
        )
        conn.commit()


def test_list_members_includes_email(store):
    owner_id = str(uuid.uuid4())
    _seed_auth_user(owner_id, "owner@acme.com")
    org = create_org("Acme", owner_id)
    members = list_members(org)
    assert len(members) == 1
    assert members[0] == {"user_id": owner_id, "role": "owner", "email": "owner@acme.com"}


def test_invite_create_list_revoke(store):
    owner_id = str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    create_invite(org, "New.Person@Example.com", "member", owner_id)
    invites = list_invites(org)
    assert len(invites) == 1
    assert invites[0]["email"] == "new.person@example.com"  # normalized lowercase

    revoke_invite(org, invites[0]["id"])
    assert list_invites(org) == []


def test_find_pending_invite_and_accept(store):
    owner_id = str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    create_invite(org, "invitee@acme.com", "member", owner_id)

    found = find_pending_invite("invitee@acme.com")
    assert found is not None and found["org_id"] == org and found["role"] == "member"

    invitee_id = str(uuid.uuid4())
    accept_invite(found["id"], invitee_id)
    assert org_for_user(invitee_id) == org
    assert find_pending_invite("invitee@acme.com") is None  # consumed


def test_reinviting_same_email_replaces_pending_invite(store):
    owner_id = str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    create_invite(org, "x@acme.com", "member", owner_id)
    create_invite(org, "x@acme.com", "owner", owner_id)  # re-invite with a different role
    invites = list_invites(org)
    assert len(invites) == 1 and invites[0]["role"] == "owner"


def test_set_member_role_and_remove_member(store):
    owner_id, member_id = str(uuid.uuid4()), str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    create_invite(org, "member@acme.com", "member", owner_id)
    accept_invite(find_pending_invite("member@acme.com")["id"], member_id)

    set_member_role(org, member_id, "owner")
    roles = {m["user_id"]: m["role"] for m in list_members(org)}
    assert roles[member_id] == "owner"

    remove_member(org, owner_id)  # fine now, two owners
    assert org_for_user(owner_id) is None


def test_cannot_remove_the_last_owner(store):
    owner_id = str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    try:
        remove_member(org, owner_id)
        assert False, "expected an error"
    except Exception as e:
        assert "owner" in str(e).lower()


def test_cannot_demote_the_last_owner(store):
    owner_id = str(uuid.uuid4())
    org = create_org("Acme", owner_id)
    try:
        set_member_role(org, owner_id, "member")
        assert False, "expected an error"
    except Exception as e:
        assert "owner" in str(e).lower()
