from teluvane import commitments


def test_canonical_payload_is_compact_and_key_sorted():
    payload = {"output": "é", "intent": "x", "args": {"b": 1, "a": 2}, "approved_by": None}
    assert commitments.canonical_payload(payload) == (
        '{"approved_by":null,"args":{"a":2,"b":1},"intent":"x","output":"é"}'
    )


def test_commit_depends_on_salt_and_payload():
    salt = commitments.new_salt()
    assert len(salt) == 64 and salt != commitments.new_salt()
    a = commitments.commit(salt, "{}")
    assert a == commitments.commit(salt, "{}")
    assert a != commitments.commit(commitments.new_salt(), "{}")
    assert a != commitments.commit(salt, '{"a":1}')
