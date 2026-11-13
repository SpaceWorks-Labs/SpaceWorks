"""Shared destinations never collapse the receiving accounts."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.integrations.models_endpoints import NotificationEndpointChallenge
from apps.integrations.notification_proofs import consume, digest, revoke, verified_callback
from apps.integrations.notification_providers import CallbackEvent, EndpointProof
from tests.notifications_contract.conftest import contract
from .p1_helpers import staff

pytestmark = pytest.mark.django_db


def bind(c, user, code):
    now = timezone.now()
    NotificationEndpointChallenge.objects.create(makerspace=c.space, user=user, configuration=c.config,
        integration_generation=c.config.generation, integration_identity=c.config.integration_identity,
        code_digest=digest(code), expires_at=now + timedelta(minutes=10), consented_at=now, consent_version="v1")
    return consume(c.config, EndpointProof(code, "shared-private", c.config.integration_identity,
                                         "shared-subject", private=True))


@pytest.mark.parametrize("staff_first", [False, True])
def test_both_accounts_independently_prove_same_identity(contract, staff_first):
    c = contract
    operator, _ = staff(c.space)
    users = [operator, c.user] if staff_first else [c.user, operator]
    endpoints = [bind(c, user, f"proof-{index}") for index, user in enumerate(users)]
    assert endpoints[0].identity_digest == endpoints[1].identity_digest
    assert {row.user_id for row in endpoints} == {operator.pk, c.user.pk}
    with pytest.raises(ValidationError):
        bind(c, users[0], "same-account-new-proof")
    for endpoint in endpoints:
        endpoint.refresh_from_db()
        assert endpoint.revoked_at is None


def test_unlink_is_account_local_and_stop_is_destination_wide(contract):
    c = contract
    operator, _ = staff(c.space)
    member_endpoint = bind(c, c.user, "member-proof")
    staff_endpoint = bind(c, operator, "staff-proof")
    revoke(member_endpoint, actor=c.user)
    staff_endpoint.refresh_from_db()
    assert staff_endpoint.revoked_at is None
    c.fake.callback = CallbackEvent(endpoint_id=staff_endpoint.pk, opt_out=True)
    # Signed callbacks remain authoritative when new delivery/proofs are disabled.
    c.config.enabled = c.config.personal_enabled = False
    c.config.save()
    verified_callback(c.config, object())
    staff_endpoint.refresh_from_db()
    assert staff_endpoint.revoked_at is not None


def test_signed_inbound_and_consent_renewal_update_both_live_bindings(contract):
    c = contract
    operator, _ = staff(c.space)
    endpoints = [bind(c, c.user, "member-proof"), bind(c, operator, "staff-proof")]
    c.fake.callback = CallbackEvent(identity_digest=endpoints[0].identity_digest, inbound=True, opt_in=True)
    verified_callback(c.config, object())
    for endpoint in endpoints:
        previous = endpoint.consented_at
        endpoint.refresh_from_db()
        assert endpoint.last_inbound_at is not None
        assert endpoint.consented_at >= previous
