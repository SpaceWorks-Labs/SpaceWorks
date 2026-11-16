"""U-C merge proofs (#65, Q16): both methods, enumeration parity, TTL, attempts, single use."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.mfa_crypto import totp
from apps.accounts.models_account_merge import AccountMergeIntent
from apps.audit.models import AuditLog
from tests.accounts.merge_helpers import (  # noqa: F401 -- fixtures
    PASSWORD, START, client_for, codes_to, converted, keys_and_clean_cache, outbox, person, proved_by_codes,
    start, url,
)
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db


def _otp(secret):
    return totp(secret, int(timezone.now().timestamp() // 30))


def test_email_codes_need_both_codes(outbox):
    survivor, source = person("pf-survivor"), converted("pf-source")
    client = client_for(survivor)
    response = start(client, source.username)
    assert response.status_code == 201 and set(response.data) == {"intent_id", "method", "state", "expires_at"}
    survivor_code = codes_to(outbox, survivor.email, "survivor")[0]
    source_code = codes_to(outbox, source.email, "source")[0]
    intent = response.data["intent_id"]
    one = client.post(url(intent, "prove"), {"survivor_code": survivor_code, "source_code": "000000"}, format="json")
    assert one.status_code == 400 and one.data["code"] == "proof_failed"
    both = client.post(url(intent, "prove"), {"survivor_code": survivor_code, "source_code": source_code},
                       format="json")
    assert both.status_code == 200 and both.data["state"] == "proved"
    row = AccountMergeIntent.objects.get(pk=intent)
    assert row.survivor_code_digest == "" and row.source_code_digest == ""  # single use


def test_same_mailbox_still_gets_two_separate_codes(outbox):
    survivor = person("pf-same", email="same@example.test")
    converted("pf-held", held_email="same@example.test")
    client = client_for(survivor)
    intent = start(client, "same@example.test").data["intent_id"]
    survivor_codes = codes_to(outbox, "same@example.test", "survivor")
    source_codes = codes_to(outbox, "same@example.test", "source")
    assert len(survivor_codes) == len(source_codes) == 1
    twice = client.post(url(intent, "prove"), {"survivor_code": survivor_codes[0],
                                               "source_code": survivor_codes[0]}, format="json")
    assert twice.status_code == 400
    ok = client.post(url(intent, "prove"), {"survivor_code": survivor_codes[0], "source_code": source_codes[0]},
                     format="json")
    assert ok.status_code == 200


def test_unknown_identifier_gets_the_same_answer(outbox):
    survivor, source = person("pf-enum"), converted("pf-enum-source")
    client = client_for(survivor)
    known = start(client, source.username)
    unknown = start(client, "nobody-here@example.test")
    assert known.status_code == unknown.status_code == 201
    assert set(known.data) == set(unknown.data) and known.data["method"] == unknown.data["method"]
    # The survivor's own code goes out either way; nothing goes to an address nobody holds.
    assert len(codes_to(outbox, survivor.email, "survivor")) == 2
    assert not codes_to(outbox, "nobody-here@example.test")
    code = codes_to(outbox, survivor.email, "survivor")[-1]
    refused = client.post(url(unknown.data["intent_id"], "prove"), {"survivor_code": code, "source_code": "123456"},
                          format="json")
    assert refused.status_code == 400 and refused.data["code"] == "proof_failed"


def test_plain_member_is_not_a_source(outbox):
    survivor, other = person("pf-m1"), person("pf-m2")
    client = client_for(survivor)
    intent = start(client, other.username).data["intent_id"]
    assert AccountMergeIntent.objects.get(pk=intent).source_id is None
    assert not codes_to(outbox, other.email)


def test_credentials_need_password_and_authenticator(outbox):
    survivor, source = person("pf-cred"), converted("pf-cred-source")
    _row, secret = enrolled(source)
    client = client_for(survivor)
    intent = start(client, source.username, "credentials").data["intent_id"]
    assert not outbox
    wrong = client.post(url(intent, "prove"), {"password": PASSWORD, "otp": "000000"}, format="json")
    assert wrong.status_code == 400 and wrong.data["code"] == "proof_failed"
    bad_password = client.post(url(intent, "prove"), {"password": "nope", "otp": _otp(secret)}, format="json")
    assert bad_password.data["code"] == "proof_failed"
    ok = client.post(url(intent, "prove"), {"password": PASSWORD, "otp": _otp(secret)}, format="json")
    assert ok.status_code == 200 and ok.data["state"] == "proved"


def test_credentials_without_a_factor_say_so_only_after_the_password(outbox):
    survivor, source = person("pf-nofactor"), converted("pf-nofactor-source")
    client = client_for(survivor)
    intent = start(client, source.username, "credentials").data["intent_id"]
    wrong = client.post(url(intent, "prove"), {"password": "nope", "otp": "123456"}, format="json")
    assert wrong.data["code"] == "proof_failed"
    right = client.post(url(intent, "prove"), {"password": PASSWORD, "otp": "123456"}, format="json")
    assert right.status_code == 409 and right.data["code"] == "factor_enrolment_required"


def test_attempts_are_capped(outbox):
    survivor, source = person("pf-cap"), converted("pf-cap-source")
    client = client_for(survivor)
    intent = start(client, source.username).data["intent_id"]
    for _ in range(5):
        client.post(url(intent, "prove"), {"survivor_code": "000000", "source_code": "000000"}, format="json")
    survivor_code = codes_to(outbox, survivor.email, "survivor")[0]
    source_code = codes_to(outbox, source.email, "source")[0]
    late = client.post(url(intent, "prove"), {"survivor_code": survivor_code, "source_code": source_code},
                       format="json")
    assert late.status_code == 410 and late.data["code"] == "proof_expired"
    assert AuditLog.objects.filter(action="account.merge_proof_failed", actor=survivor).count() == 5


def test_codes_expire_after_ten_minutes(outbox):
    survivor, source = person("pf-ttl"), converted("pf-ttl-source")
    client = client_for(survivor)
    response = start(client, source.username)
    intent = AccountMergeIntent.objects.get(pk=response.data["intent_id"])
    assert timedelta(minutes=9) < intent.expires_at - timezone.now() <= timedelta(minutes=10)
    AccountMergeIntent.objects.filter(pk=intent.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    late = client.post(url(intent.pk, "prove"), {"survivor_code": codes_to(outbox, survivor.email, "survivor")[0],
                                                 "source_code": codes_to(outbox, source.email, "source")[0]},
                       format="json")
    assert late.status_code == 410 and late.data["code"] == "proof_expired"


def test_resend_replaces_codes_and_cancel_ends_the_intent(outbox):
    survivor, source = person("pf-resend"), converted("pf-resend-source")
    client = client_for(survivor)
    intent = start(client, source.username).data["intent_id"]
    old = (codes_to(outbox, survivor.email, "survivor")[0], codes_to(outbox, source.email, "source")[0])
    assert client.post(url(intent, "resend")).status_code == 200
    stale = client.post(url(intent, "prove"), {"survivor_code": old[0], "source_code": old[1]}, format="json")
    assert stale.status_code == 400
    assert client.post(url(intent, "cancel")).data["state"] == "cancelled"
    assert client.post(url(intent, "resend")).status_code == 410


def test_audit_never_holds_codes_or_identifiers(outbox):
    survivor, source = person("pf-audit"), converted("pf-audit-source")
    client = client_for(survivor)
    proved_by_codes(client, outbox, survivor, source.email, source.username)
    rows = AuditLog.objects.filter(action__startswith="account.merge")
    assert rows.exists()
    blob = repr(list(rows.values_list("meta", flat=True)))
    for secret in (source.username, source.email, *codes_to(outbox, survivor.email)):
        assert secret not in blob


def test_start_is_throttled(outbox, monkeypatch):
    from apps.accounts.views_account_merge import AccountMergeStartThrottle

    monkeypatch.setattr(AccountMergeStartThrottle, "THROTTLE_RATES", {"account_merge_start": "2/hour"})
    client = client_for(person("pf-throttle"))
    assert [start(client, "x").status_code for _ in range(3)] == [201, 201, 429]


def test_only_the_survivor_reads_its_intent(outbox):
    survivor, other, source = person("pf-own"), person("pf-other"), converted("pf-own-source")
    intent = start(client_for(survivor), source.username).data["intent_id"]
    assert client_for(other).post(url(intent, "prove"), {"survivor_code": "1", "source_code": "2"},
                                  format="json").status_code == 404
    assert START.endswith("start")
