from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.integrations.notification_proofs import consume, start, verified_callback
from apps.integrations.notification_providers import CallbackEvent, EndpointProof

pytestmark = pytest.mark.django_db


def challenge(c):
    row, response = start(c.user, c.config, "v1")
    code = parse_qs(urlsplit(response["connect_url"]).query)["code"][0]
    return row, EndpointProof(code, "private-new", c.config.integration_identity, "subject-new", private=True)


def test_single_use_binds_account_tenant_integration(contract):
    c = contract
    row, proof = challenge(c)
    assert row.code_digest != proof.code
    endpoint = consume(c.config, proof, expected_user_id=c.user.pk, expected_challenge_id=row.pk)
    assert endpoint.user == c.user and endpoint.makerspace == c.space
    assert endpoint.provider_subject == "subject-new"
    with pytest.raises(ValidationError):
        consume(c.config, proof)


@pytest.mark.parametrize("failure", ["expired", "rotated", "wrong_user", "wrong_integration", "group_chat", "exhausted"])
def test_invalid_proof_cannot_create_endpoint(contract, failure):
    from dataclasses import replace
    c = contract
    row, proof = challenge(c)
    kwargs = {}
    if failure == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
    elif failure == "rotated":
        c.config.generation += 1
        c.config.save()
    elif failure == "wrong_user":
        kwargs["expected_user_id"] = c.user.pk + 100
    elif failure == "wrong_integration":
        proof = replace(proof, integration_identity="other-bot")
    elif failure == "group_chat":
        proof = replace(proof, private=False)
    else:
        row.attempts = 5
        row.save()
    with pytest.raises(ValidationError):
        consume(c.config, proof, **kwargs)
    row.refresh_from_db()
    assert row.endpoint_id is None


def test_failed_attempt_persists_and_start_is_throttled(contract):
    c = contract
    row, proof = challenge(c)
    with pytest.raises(ValidationError):
        consume(c.config, proof, expected_user_id=c.user.pk + 1)
    row.refresh_from_db()
    assert row.attempts == 1
    with pytest.raises(Throttled):
        start(c.user, c.config, "v1")


def test_bad_code_against_bound_challenge_consumes_attempt(contract):
    from dataclasses import replace
    c = contract
    row, proof = challenge(c)
    with pytest.raises(ValidationError):
        consume(c.config, replace(proof, code="wrong-code"), expected_user_id=c.user.pk,
                expected_challenge_id=row.pk)
    row.refresh_from_db()
    assert row.attempts == 1 and row.endpoint_id is None


def test_unsigned_callback_cannot_verify_or_revoke(contract):
    c = contract
    c.fake.callback = None
    with pytest.raises(ValidationError):
        verified_callback(c.config, object())
    c.endpoint.refresh_from_db()
    assert c.endpoint.revoked_at is None


def test_verified_provider_opt_out_revokes(contract):
    c = contract
    c.fake.callback = CallbackEvent(endpoint_id=c.endpoint.pk, opt_out=True)
    verified_callback(c.config, object())
    c.endpoint.refresh_from_db()
    assert c.endpoint.revoked_at is not None


def test_only_verified_inbound_updates_whatsapp_window(contract):
    c = contract
    assert c.endpoint.last_inbound_at is None
    c.fake.callback = CallbackEvent(endpoint_id=c.endpoint.pk, inbound=True)
    verified_callback(c.config, object())
    c.endpoint.refresh_from_db()
    assert c.endpoint.last_inbound_at is not None
