"""SECFIX-A F1: domain-separated, length-framed signatures (lead 10), the canonical signed-time nonce, the offline
cache bounded by grant expiry (hardening #3) and bounded, flagged offline decisions (L-A3)."""
import time
import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterAccessCache, AdapterAccessLog
from apps.devices.services_adapter_core import CACHE_DOMAIN, TIME_DOMAIN, credential_digest, framed, sign
from tests.adapter_conformance.conformance import cache_message, time_message, verify_ed25519
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)
CACHE_CAPS = ("status", "events", "access.authorize", "access.cache")
TAG = "04A1B2C3D4"
NONCE = "f1-adapter-nonce-0001"


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()


def _digests(doc):
    return [row["digest"] for row in doc["entries"]]


def _cache_case(slug, *, grant_ends=None, grant=True):
    from apps.machines.models import MachineAccessGrant
    case = adapter_case(slug, caps=CACHE_CAPS)
    member = plain_member(f"{slug}-m", case["space"])
    made = case["client"].post(reverse("devices:admin-adapter-credentials", args=[case["space"].pk]),
                               {"user_id": member.pk, "kind": "nfc", "secret": TAG}, format="json")
    assert made.status_code == 201, made.data
    if grant:
        MachineAccessGrant.objects.create(makerspace=case["space"], member=member, machine=case["machine"],
                                          expires_at=grant_ends)
    case["member"] = member
    return case


def _fetch(case):
    return case["sim"].get(f"access/cache?binding_id={case['binding_id']}").data


# --- lead 10: framing and domain separation ----------------------------------------------------------------------
def test_framing_is_the_domain_a_nul_then_length_prefixed_fields():
    assert framed("d", "ab", 12) == b"d\x00" + b"\x00\x00\x00\x02ab" + b"\x00\x00\x00\x0212"
    # Without length framing these two would be the same bytes; with it they are not.
    assert framed(CACHE_DOMAIN, "a.b", "c") != framed(CACHE_DOMAIN, "a", "b.c")
    with pytest.raises(TypeError):
        sign("an unframed string")


def test_the_cache_signature_verifies_only_as_a_framed_cache_message():
    case = _cache_case("f1-sig-cache")
    keys = case["sim"].hello(list(CACHE_CAPS)).data["cache_keys"]
    doc = _fetch(case)
    assert _digests(doc) == [credential_digest(case["space"].pk, "nfc", TAG)]
    assert verify_ed25519(keys, doc["kid"], cache_message(doc, _digests(doc)), doc["signature"])
    legacy = (f"{doc['binding_id']}.{doc['kid']}.{doc['version']}.{doc['issued_at']}.{doc['expires_at']}.")
    assert not verify_ed25519(keys, doc["kid"], legacy, doc["signature"])  # the old undelimited string no longer verifies


def test_a_signed_time_cannot_be_replayed_as_a_cache_and_echoes_the_adapters_nonce():
    case = _cache_case("f1-sig-time")
    keys = case["sim"].hello(list(CACHE_CAPS)).data["cache_keys"]
    body = case["sim"].get(f"time?nonce={NONCE}").data
    assert body["nonce"] == NONCE
    assert verify_ed25519(keys, body["kid"], time_message(NONCE, body["kid"], body["server_time"]), body["signature"])
    # The same fields under the cache domain (what a cross-protocol replay would need) do not verify.
    assert not verify_ed25519(keys, body["kid"], framed(CACHE_DOMAIN, NONCE, body["kid"], body["server_time"]),
                              body["signature"])
    assert framed(TIME_DOMAIN, NONCE, body["kid"], body["server_time"]) == time_message(NONCE, body["kid"],
                                                                                         body["server_time"])


@pytest.mark.parametrize("nonce", ["", "abc123", "x" * 15, "x" * 65, "bad.nonce.with.dots.0", "a" * 15 + "!"])
def test_signed_time_requires_a_canonical_adapter_nonce(nonce):
    case = adapter_case(f"f1-nonce-{len(nonce)}-{nonce[:3].strip() or 'e'}", caps=CACHE_CAPS)
    response = case["sim"].get(f"time?nonce={nonce}" if nonce else "time")
    assert response.status_code == 400 and response.data["code"] == "invalid_nonce"


@pytest.mark.parametrize("nonce", ["x" * 16, "Ab_-" * 16])
def test_signed_time_accepts_16_to_64_url_safe_characters(nonce):
    case = adapter_case(f"f1-nonce-ok-{len(nonce)}", caps=CACHE_CAPS)
    response = case["sim"].get(f"time?nonce={nonce}")
    assert response.status_code == 200 and response.data["nonce"] == nonce


# --- hardening #3: the list never outlives a grant ----------------------------------------------------------------
def test_a_grant_ending_soon_shortens_the_whole_list_to_its_end():
    ends = timezone.now() + timedelta(minutes=5)
    case = _cache_case("f1-grant-soon", grant_ends=ends)
    doc = _fetch(case)
    assert len(doc["entries"]) == 1
    assert doc["expires_at"] == int(ends.timestamp()) and doc["expires_at"] - doc["issued_at"] < 900
    assert AdapterAccessCache.objects.get(binding_id=case["binding_id"]).entry_count == 1


def test_a_grant_ending_within_a_minute_is_left_out_and_an_open_grant_keeps_the_full_ttl():
    case = _cache_case("f1-grant-gone", grant_ends=timezone.now() + timedelta(seconds=20))
    doc = _fetch(case)
    assert doc["entries"] == [] and doc["expires_at"] - doc["issued_at"] == 900
    open_case = _cache_case("f1-grant-open")
    doc = _fetch(open_case)
    assert len(doc["entries"]) == 1 and doc["expires_at"] - doc["issued_at"] == 900


# --- L-A3: offline decisions are bounded and flagged -------------------------------------------------------------
def _report(case, *, digest, allowed=True, decided_at=None):
    item = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "allowed": allowed,
            "decided_at": decided_at or int(time.time()) - 60}
    if digest:
        item["digest"] = digest
    response = case["sim"].post("access/offline-decisions", {"decisions": [item]})
    assert response.status_code == 200, response.data
    return item["operation_id"], response.data["results"][0]


def _flags():
    return list(AuditLog.objects.filter(action="devices.adapter_offline_decision_flagged").values_list(
        "meta__flag", flat=True))


def test_an_allow_from_the_issued_cache_is_stored_without_a_flag_and_the_receive_time_is_audited():
    case = _cache_case("f1-offline-ok")
    _fetch(case)
    operation, result = _report(case, digest=credential_digest(case["space"].pk, "nfc", TAG))
    assert result == {"operation_id": operation, "result": "stored"}
    assert AdapterAccessLog.objects.get(offline=True).member_id == case["member"].pk
    assert _flags() == []
    audit = AuditLog.objects.get(action="devices.adapter_offline_decisions_reconciled")
    assert audit.meta["operation_ids"] == [operation] and abs(audit.meta["received_at"] - time.time()) < 60


def test_a_back_dated_decision_is_rejected_and_never_stored():
    case = _cache_case("f1-offline-old")
    _fetch(case)
    _operation, result = _report(case, digest=credential_digest(case["space"].pk, "nfc", TAG),
                                 decided_at=int(time.time()) - 8 * 86400)
    assert result["result"] == "rejected" and result["code"] == "decided_too_old"
    assert not AdapterAccessLog.objects.filter(offline=True).exists()


def test_an_allow_for_a_digest_that_was_never_live_here_is_stored_and_flagged():
    case = _cache_case("f1-offline-forged")
    _fetch(case)
    _operation, result = _report(case, digest="f" * 64)
    assert result["result"] == "stored" and _flags() == ["digest_not_in_cache"]


def test_an_allow_with_no_cache_issued_or_after_it_expired_is_flagged_but_a_denial_never_is():
    digest_of = lambda case: credential_digest(case["space"].pk, "nfc", TAG)  # noqa: E731
    never = _cache_case("f1-offline-nocache")
    _report(never, digest=digest_of(never))
    assert _flags() == ["no_cache_issued"]
    expired = _cache_case("f1-offline-expired")
    _fetch(expired)
    AdapterAccessCache.objects.filter(binding_id=expired["binding_id"]).update(
        issued_at=timezone.now() - timedelta(hours=3), expires_at=timezone.now() - timedelta(hours=2))
    _report(expired, digest=digest_of(expired))
    assert sorted(_flags()) == ["cache_expired", "no_cache_issued"]
    _report(expired, digest="e" * 64, allowed=False)
    assert len(_flags()) == 2
