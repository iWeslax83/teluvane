import time

from teluvane.pii import find_pii, has_sensitive


def kinds(t):
    return {h.kind for h in find_pii(t)}


def test_ssn():
    assert "ssn" in kinds("SSN 123-45-6789 on file")
    assert "ssn" not in kinds("order 000-12-3456")


def test_card_luhn():
    assert "card" in kinds("card 4111 1111 1111 1111")
    assert "card" not in kinds("ref 4111 1111 1111 1112")


def test_iban():
    assert "iban" in kinds("pay to GB82 WEST 1234 5698 7654 32")
    assert "iban" not in kinds("code GB82 WEST 1234 5698 7654 33")


def test_tckn():
    assert "tckn" in kinds("kimlik 10000000146")
    assert "tckn" not in kinds("kimlik 10000000147")
    assert "tckn" not in kinds("order 12345678901")


def test_email_not_sensitive():
    assert kinds("to ops@acme.com") == {"email"}
    assert not has_sensitive("to ops@acme.com")


def test_secret():
    assert has_sensitive("key AKIAIOSFODNN7EXAMPLE")
    assert has_sensitive("-----BEGIN RSA PRIVATE KEY-----")
    assert not has_sensitive("plain text")


def test_scan_stays_fast_on_hostile_input():
    # Unbounded email local-part matching made this quadratic (14 s for 100 KB).
    for text in ("a-" * 100_000, "a." * 100_000, "1-" * 50_000):
        start = time.perf_counter()
        find_pii(text)
        assert time.perf_counter() - start < 1.0


def test_millisecond_timestamps_are_not_cards():
    # About one in ten 13-digit numbers passes Luhn; real issuers start with 2 to 6.
    for n in range(1695800000000, 1695800000100):
        assert "card" not in kinds(f'{{"ts": {n}}}'), n
