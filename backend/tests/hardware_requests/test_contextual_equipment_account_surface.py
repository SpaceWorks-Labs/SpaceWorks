"""The account surface must admit the same delegate the equipment view authorizes."""
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import mfa_policy, rbac
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.events.models import EventRegistration
from apps.events.services_staff_grants import revoke_grant
from apps.hardware_requests.models import HardwareRequest
from tests.accounts.mfa_helpers import enrolled
from tests.encryption.conftest import enabled_encryption
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account
from tests.return_helpers import make_product


@pytest.mark.django_db(transaction=True)
def test_verified_session_delegate_can_propose_without_inventory_authority():
    space, manager, delegate, event, grant = grant_fixture("manage_registrations")
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    borrower = account("surface-equipment-borrower")
    registration = EventRegistration.objects.create(event=event, member=borrower, name="Borrower",
        email=borrower.email, status=EventRegistration.Status.REGISTERED)
    product = make_product(space)
    assert not rbac.can(delegate, rbac.Action.EDIT_INVENTORY, space.pk)
    assert not rbac.can(delegate, rbac.Action.ACCEPT_REQUEST, space.pk)
    client = APIClient()
    with enabled_encryption():
        credential, _ = enrolled(delegate)
        mfa_policy.stamp(delegate, credential, "totp")
        token = SpaceWorksRefreshToken.for_user(delegate).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN="http://localhost:5000")
        url = reverse("hardware_requests:contextual-request-staff", args=[space.pk])
        body = {"event_registration_id": registration.pk, "requested_for": "Workshop",
                "items": [{"product_id": product.pk, "quantity": 1}]}
        created = client.post(url, {**body, "operation_id": str(uuid4())}, format="json")
        assert created.status_code == 201, created.content
        request = HardwareRequest.objects.get(pk=created.data["request_id"])
        assert request.requester_id == borrower.pk and request.status == HardwareRequest.Status.PENDING_APPROVAL
        assert client.post(reverse("hardware_requests:request-accept", args=[request.pk]), {},
                           format="json").status_code in (403, 404)
        revoke_grant(grant, actor=manager)
        refused = client.post(url, {**body, "operation_id": str(uuid4())}, format="json")
        assert refused.status_code in (403, 404), refused.content
        assert HardwareRequest.objects.filter(makerspace=space, requester=borrower).count() == 1
