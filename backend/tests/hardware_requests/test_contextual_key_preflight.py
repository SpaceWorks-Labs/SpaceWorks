from unittest.mock import Mock
from uuid import uuid4
from contextlib import nullcontext

import pytest
from django.http import Http404

from apps.events.models import EventRegistration
from apps.hardware_requests import contextual_equipment_service as service
from apps.accounts.models import User
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account
from tests.return_helpers import make_product, make_space, make_user


@pytest.mark.django_db(transaction=True)
def test_disabled_event_source_cannot_provision_key(monkeypatch):
    maker, _manager, actor, event, _grant = grant_fixture("manage_registrations")
    borrower = account("contextual-disabled-borrower")
    registration = EventRegistration.objects.create(
        event=event, member=borrower, name="Borrower", email=borrower.email, phone="12345678",
        status=EventRegistration.Status.REGISTERED,
    )
    product = make_product(maker, is_public=True)
    maker.enabled_modules = [name for name in maker.enabled_modules if name != "events"]
    maker.save(update_fields=["enabled_modules"])
    prepare = Mock(side_effect=AssertionError("key must not be provisioned"))
    monkeypatch.setattr(service, "prepare_tenant_key", prepare)
    with pytest.raises(Http404):
        service.create_pending(
            makerspace_id=maker.pk, actor=actor, borrower=None, intent_kind="staff", operation_id=uuid4(),
            event_registration_id=registration.pk, booking_id=None, booking_token=None, borrower_id=None,
            items=[{"product_id": product.pk, "quantity": 1}], kit=None, requested_for="",
            pickup_from=None, pickup_until=None, waitlist_entry_id=None,
            canonical_fields={"items": [{"product_id": product.pk, "quantity": 1}]},
        )
    prepare.assert_not_called()


def test_missing_authenticated_actor_refuses_before_key_preparation(monkeypatch):
    actor = Mock(is_authenticated=True, pk=42)
    actor.refresh_from_db.side_effect = User.DoesNotExist()
    prepare = Mock(side_effect=AssertionError("key must not be provisioned"))
    monkeypatch.setattr(service, "boundary_tenant_write", lambda _: nullcontext())
    monkeypatch.setattr(service, "prepare_tenant_key", prepare)
    with pytest.raises(Http404):
        service.create_pending(makerspace_id=1, actor=actor)
    prepare.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(("site", "inventory"), [(False, True), (True, False)])
def test_private_member_catalogue_cannot_provision_key(monkeypatch, site, inventory):
    maker = make_space("private-intake-key")
    maker.public_site_enabled, maker.public_inventory_enabled = site, inventory
    maker.save(update_fields=["public_site_enabled", "public_inventory_enabled"])
    actor = make_user("private-intake-key-actor")
    prepare = Mock(side_effect=AssertionError("key must not be provisioned"))
    monkeypatch.setattr(service, "prepare_tenant_key", prepare)
    with pytest.raises(Http404):
        service.create_pending(
            makerspace_id=maker.pk, actor=actor, borrower=actor, intent_kind="self", operation_id=uuid4(),
            event_registration_id=None, booking_id=None, booking_token=None, borrower_id=None,
            items=[{"product_id": 1, "quantity": 1}], kit=None, requested_for="",
            pickup_from=None, pickup_until=None, waitlist_entry_id=None,
            canonical_fields={"items": [{"product_id": 1, "quantity": 1}]},
        )
    prepare.assert_not_called()
