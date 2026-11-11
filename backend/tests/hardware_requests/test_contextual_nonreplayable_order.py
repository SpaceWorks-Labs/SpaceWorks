"""No optional selector lookup may precede the sticky receipt refusal."""
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import nullcontext

import pytest
from django.http import Http404

from apps.hardware_requests import contextual_equipment_service as service
from tests.return_helpers import make_space, make_user


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["self", "staff"])
def test_nonreplayable_stops_before_booking_or_borrower_lookup(monkeypatch, kind):
    maker = make_space("sticky-receipt")
    actor = make_user("sticky-actor")
    monkeypatch.setattr(service, "assert_write_allowed", lambda _: None)
    monkeypatch.setattr(service, "assert_mapped_write_allowed", lambda _: None)
    monkeypatch.setattr(service, "boundary_tenant_write", lambda _: nullcontext())
    query = SimpleNamespace(values_list=lambda *_args, **_kwargs: SimpleNamespace(first=lambda: (True, None)))
    monkeypatch.setattr(service.EquipmentProposalReceipt.objects, "filter", lambda **_: query)
    booking_lookup = Mock(side_effect=AssertionError("booking lookup ran"))
    event_lookup = Mock(side_effect=AssertionError("event lookup ran"))
    user_lookup = Mock(side_effect=AssertionError("borrower lookup ran"))
    monkeypatch.setattr(service.bridge, "member_booking_id", booking_lookup)
    monkeypatch.setattr(service.bridge, "observe_event", event_lookup)
    monkeypatch.setattr(service.User.objects, "get", user_lookup)
    with pytest.raises(Http404):
        service.create_pending(
            makerspace_id=maker.pk, actor=actor, borrower=actor if kind == "self" else None,
            intent_kind=kind, operation_id="381091a1-0f99-4d3f-9464-55f40986864e",
            event_registration_id=None if kind == "self" else 10,
            booking_id=None, booking_token="fb4c7c7a-e585-4417-a290-23b6b9d37b0b" if kind == "self" else None,
            borrower_id=42 if kind == "staff" else None,
            items=[{"product_id": 1, "quantity": 1}], kit=None, requested_for="",
            pickup_from=None, pickup_until=None, waitlist_entry_id=None,
            canonical_fields={"items": [{"product_id": 1, "quantity": 1}]},
        )
    booking_lookup.assert_not_called()
    event_lookup.assert_not_called()
    user_lookup.assert_not_called()
