from teluvane.orgs import create_org, org_for_user


def test_create_org_makes_owner_member(store):  # `store` fixture truncates events/verdicts
    org_id = create_org("Acme", "user-123")
    assert org_id.startswith("org_")
    assert org_for_user("user-123") == org_id


def test_org_for_user_unknown_returns_none():
    assert org_for_user("nobody-xyz") is None
