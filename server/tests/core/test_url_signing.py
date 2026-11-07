from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core import url_signing
from image_edit_server.core.url_signing import RESULT_URL_TTL, sign, verify

SECRET = b"unit-test-secret-0123456789abcdef"
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
JOB = "01HZZZZZZZZZZZZZZZZZZZZZZA"
EXP = int((NOW + RESULT_URL_TTL).timestamp())


def test_the_lifetime_is_fifteen_minutes():
    assert RESULT_URL_TTL == timedelta(minutes=15)


def test_a_signature_verifies_before_it_expires():
    assert verify(JOB, EXP, sign(JOB, EXP, SECRET), SECRET, NOW)


def test_an_expired_link_is_refused():
    signature = sign(JOB, EXP, SECRET)

    assert not verify(JOB, EXP, signature, SECRET, NOW + timedelta(minutes=16))
    assert not verify(JOB, EXP, signature, SECRET, datetime.fromtimestamp(EXP, timezone.utc))


def test_a_changed_expiry_is_refused():
    signature = sign(JOB, EXP, SECRET)

    assert not verify(JOB, EXP + 3600, signature, SECRET, NOW)


def test_another_jobs_signature_is_refused():
    other = sign("01HZZZZZZZZZZZZZZZZZZZZZZB", EXP, SECRET)

    assert not verify(JOB, EXP, other, SECRET, NOW)


def test_a_wrong_secret_is_refused():
    assert not verify(JOB, EXP, sign(JOB, EXP, b"another-secret-0123456789abcdefgh"), SECRET, NOW)


@pytest.mark.parametrize("bad", ["", "not base64 !!", "abc", "é" * 43, "A" * 500])
def test_a_malformed_signature_is_refused(bad):
    assert not verify(JOB, EXP, bad, SECRET, NOW)


def test_the_signature_is_unpadded_base64url():
    signature = sign(JOB, EXP, SECRET)

    assert len(signature) == 43
    assert set(signature) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def test_signatures_are_compared_in_constant_time(monkeypatch):
    calls = []
    real = url_signing.hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(url_signing.hmac, "compare_digest", spy)

    verify(JOB, EXP, sign(JOB, EXP, SECRET), SECRET, NOW)

    assert len(calls) == 1
