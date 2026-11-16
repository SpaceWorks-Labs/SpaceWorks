"""Lane S0: emailed login-code primitives (digest binding, constant-time verify, TTL, attempts)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts import login_codes


def test_new_codes_are_six_digits_and_vary():
    codes = {login_codes.new_code() for _ in range(200)}
    assert all(len(code) == 6 and code.isdigit() for code in codes)
    assert len(codes) > 150


def test_digest_binds_purpose_and_subject():
    stored = login_codes.digest("123456", "login", "user:7")
    assert len(stored) == 64 and "123456" not in stored
    assert login_codes.verify(stored, "123456", "login", "user:7")
    assert login_codes.verify(stored, "123 456", "login", "user:7")
    assert login_codes.verify(stored, "123-456", "login", "user:7")
    assert not login_codes.verify(stored, "123457", "login", "user:7")
    assert not login_codes.verify(stored, "123456", "risk", "user:7")
    assert not login_codes.verify(stored, "123456", "login", "user:8")


def test_digest_depends_on_the_secret_key(settings):
    before = login_codes.digest("123456", "login", "1")
    settings.SECRET_KEY = "another-secret-key-for-this-test-only"
    assert login_codes.digest("123456", "login", "1") != before


@pytest.mark.parametrize("bad", ["", "12345", "1234567", "abcdef", "١٢٣٤٥٦", None, 123456])
def test_malformed_codes_never_verify(bad):
    stored = login_codes.digest("123456", "login", "1")
    assert login_codes.verify(stored, bad, "login", "1") is False
    assert login_codes.verify("", "123456", "login", "1") is False


def test_digest_refuses_bad_labels_and_codes():
    with pytest.raises(ValueError):
        login_codes.digest("12345", "login", "1")
    with pytest.raises(ValueError):
        login_codes.digest("123456", "", "1")
    with pytest.raises(ValueError):
        login_codes.digest("123456", "login", "a\x00b")


def test_verify_uses_a_constant_time_comparison(monkeypatch):
    calls = []
    monkeypatch.setattr(login_codes, "constant_time_compare", lambda a, b: calls.append((a, b)) or a == b)
    stored = login_codes.digest("654321", "login", "1")
    assert login_codes.verify(stored, "654321", "login", "1")
    assert calls and calls[0][0] == stored


def test_ttl_and_attempt_helpers(settings):
    settings.LOGIN_CODE_TTL_SECONDS = 600
    now = timezone.now()
    expiry = login_codes.expires_at(now)
    assert expiry == now + timedelta(seconds=600)
    assert login_codes.expires_at(now, ttl_seconds=60) == now + timedelta(seconds=60)
    assert not login_codes.is_expired(expiry, now)
    assert login_codes.is_expired(expiry, expiry)
    assert login_codes.is_expired(None, now)
    assert not login_codes.attempts_exhausted(4) and login_codes.attempts_exhausted(5)
    assert login_codes.attempts_left(3) == 2 and login_codes.attempts_left(9) == 0
