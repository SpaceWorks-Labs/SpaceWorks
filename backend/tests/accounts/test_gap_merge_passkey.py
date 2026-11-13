"""GAP2 M6 (#65): the other account's passkey stands in for its authenticator code in a merge proof.
Local only. The WebAuthn ceremony itself is S-A's (tested there); it is stubbed here at its seam."""

import uuid
from types import SimpleNamespace

import pytest

from apps.accounts.models_account_merge import AccountMergeIntent
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.audit.models import AuditLog
from tests.accounts.merge_helpers import (  # noqa: F401 -- fixtures
    PASSWORD, client_for, converted, keys_and_clean_cache, person, start, url,
)

pytestmark = pytest.mark.django_db
GOOD = str(uuid.uuid4())


@pytest.fixture
def ceremony(monkeypatch):
    calls = {"begin": [], "verify": []}

    def begin_proof(request, account):
        calls["begin"].append(account.pk)
        return SimpleNamespace(pk=uuid.UUID(GOOD)), '{"challenge": "abc", "allowCredentials": []}'

    def verify_proof(request, account, ceremony_id, credential):
        calls["verify"].append((account.pk, str(ceremony_id)))
        return str(ceremony_id) == GOOD and credential == {"id": "cred-1"}

    monkeypatch.setattr("apps.accounts.passkeys.assertion.begin_proof", begin_proof)
    monkeypatch.setattr("apps.accounts.passkeys.assertion.verify_proof", verify_proof)
    monkeypatch.setattr("apps.accounts.passkeys.rp_id.request_origin_and_rp_id",
                        lambda request: ("https://space.test", "space.test"))
    return calls


def with_passkey(user, rp_id="space.test"):
    WebAuthnCredential.objects.create(user=user, credential_id=f"cred-{user.pk}", public_key=b"k", rp_id=rp_id)
    return user


def intent_for(survivor, source):
    client = client_for(survivor)
    response = start(client, source.username, method="credentials")
    assert response.status_code == 201
    return client, response.data["intent_id"]


def test_password_then_passkey_proves_the_other_account(ceremony):
    survivor, source = person("gp-survivor"), with_passkey(converted("gp-source"))
    client, intent = intent_for(survivor, source)
    options = client.post(url(intent, "passkey-options"), {"password": PASSWORD}, format="json")
    assert options.status_code == 200, options.content
    assert options.data["ceremony"] == uuid.UUID(GOOD) and options.data["options"]["challenge"] == "abc"
    assert options["Cache-Control"] == "private, no-store"
    assert ceremony["begin"] == [source.pk]
    proved = client.post(url(intent, "prove"), {"password": PASSWORD, "passkey": {
        "ceremony": GOOD, "credential": {"id": "cred-1"}}}, format="json")
    assert proved.status_code == 200 and proved.data["state"] == "proved"
    assert ceremony["verify"] == [(source.pk, GOOD)]


def test_a_wrong_password_offers_nothing_and_counts_as_a_failed_try(ceremony):
    survivor, source = person("gp-wrong"), with_passkey(converted("gp-wrong-src"))
    client, intent = intent_for(survivor, source)
    response = client.post(url(intent, "passkey-options"), {"password": "nope"}, format="json")
    assert response.status_code == 400 and response.data["code"] == "proof_failed"
    assert ceremony["begin"] == []
    assert AccountMergeIntent.objects.get(pk=intent).attempts == 1
    assert AuditLog.objects.filter(action="account.merge_proof_failed").exists()


def test_an_unknown_account_answers_like_a_wrong_password(ceremony):
    survivor = person("gp-unknown")
    client = client_for(survivor)
    intent = start(client, "nobody-here", method="credentials").data["intent_id"]
    response = client.post(url(intent, "passkey-options"), {"password": PASSWORD}, format="json")
    assert response.status_code == 400 and response.data["code"] == "proof_failed"


def test_no_passkey_on_this_address_says_factor_enrolment_required_only_after_the_password(ceremony):
    survivor, source = person("gp-none"), with_passkey(converted("gp-none-src"), rp_id="elsewhere.test")
    client, intent = intent_for(survivor, source)
    response = client.post(url(intent, "passkey-options"), {"password": PASSWORD}, format="json")
    assert response.status_code == 409
    assert response.data["code"] == "factor_enrolment_required"
    assert ceremony["begin"] == []


def test_passkeys_turned_off_for_the_source_refuse_the_passkey_route(ceremony, monkeypatch):
    monkeypatch.setattr("apps.accounts.passkeys.policy.passkeys_usable", lambda user: False)
    survivor, source = person("gp-off"), with_passkey(converted("gp-off-src"))
    client, intent = intent_for(survivor, source)
    response = client.post(url(intent, "passkey-options"), {"password": PASSWORD}, format="json")
    assert response.data["code"] == "factor_enrolment_required"


def test_a_wrong_ceremony_or_password_fails_the_proof_and_is_counted(ceremony):
    survivor, source = person("gp-bad"), with_passkey(converted("gp-bad-src"))
    client, intent = intent_for(survivor, source)
    bad = client.post(url(intent, "prove"), {"password": PASSWORD, "passkey": {
        "ceremony": str(uuid.uuid4()), "credential": {"id": "cred-1"}}}, format="json")
    assert bad.status_code == 400 and bad.data["code"] == "proof_failed"
    wrong_password = client.post(url(intent, "prove"), {"password": "nope", "passkey": {
        "ceremony": GOOD, "credential": {"id": "cred-1"}}}, format="json")
    assert wrong_password.status_code == 400
    assert AccountMergeIntent.objects.get(pk=intent).attempts == 2
    assert ceremony["verify"] == [(source.pk, ceremony["verify"][0][1])]  # the wrong password never reached it


def test_the_email_codes_method_has_no_passkey_route(ceremony):
    survivor, source = person("gp-codes"), with_passkey(converted("gp-codes-src"))
    client = client_for(survivor)
    intent = start(client, source.username, method="email_codes").data["intent_id"]
    response = client.post(url(intent, "passkey-options"), {"password": PASSWORD}, format="json")
    assert response.data["code"] == "proof_expired"


def test_the_route_is_member_only_and_refused_to_claim_sessions():
    from apps.accounts.claim_routes_r2 import _REFUSED
    from apps.accounts.delegated_route_catalog import ACCOUNT_MERGE_ROUTES
    assert "auth-account-merge-passkey-options" in ACCOUNT_MERGE_ROUTES
    refused = {name for _reason, routes in _REFUSED for name, _methods in routes}
    assert "auth-account-merge-passkey-options" in refused
