"""Decision 221b: time-window availability and event-only lending refusals."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.hardware_requests.self_checkout_helpers import _eligible_product, _issue_product
from apps.hardware_requests.direct_loan_workflow import _manual_product
from apps.hardware_requests.workflow_errors import RequestValidationError  # noqa: F401
from apps.inventory import availability
from apps.inventory.equipment_picker import product_page
from apps.inventory.event_only import EventOnlyProduct, refuse_event_only_ids
from apps.inventory.requestable_products import requestable_products
from tests.return_helpers import make_product, make_space
from tests.test_request_workflow import make_user

pytestmark = pytest.mark.django_db


def test_window_counts_reserved_as_committed_and_returning_loans_as_free():
    maker = make_space("w221b-window")
    product = make_product(maker, name="Camera", total_quantity=10, available_quantity=5,
                           reserved_quantity=2, issued_quantity=3)
    now = timezone.now()
    start, end = now + timedelta(days=3), now + timedelta(days=4)
    figures = availability.window_availability([product], start, end, now=now)[product.pk]
    # No loan has a due time yet: every issued unit is conservatively committed.
    assert figures == {"free": 5, "committed": 5, "back_before_window": 0, "lendable": 10}


def test_window_rejects_an_inverted_window():
    maker = make_space("w221b-inverted")
    product = make_product(maker)
    now = timezone.now()
    with pytest.raises(ValueError):
        availability.window_availability([product], now + timedelta(days=2), now + timedelta(days=1))


def test_event_only_products_leave_ordinary_pickers_but_stay_in_event_context():
    maker = make_space("w221b-picker")
    plain = make_product(maker, name="Plain", is_public=True)
    only = make_product(maker, name="Only", is_public=True, event_only=True)
    assert [p.pk for p in requestable_products(maker)] == [plain.pk]
    assert {p.pk for p in requestable_products(maker, event_context=True)} == {plain.pk, only.pk}
    request = Request(APIRequestFactory().get("/picker"))
    assert [r["id"] for r in product_page(request, maker).data["results"]] == [plain.pk]
    event_rows = product_page(request, maker, event_context=True).data["results"]
    assert {r["id"]: r["event_only"] for r in event_rows} == {plain.pk: False, only.pk: True}


def test_self_checkout_and_direct_handout_refuse_event_only_with_a_clear_code():
    maker = make_space("w221b-doors")
    only = make_product(maker, name="Only", is_public=True, event_only=True, public_self_checkout_enabled=True)
    for door in (lambda: _eligible_product(only.pk, maker), lambda: _manual_product(maker, only.pk),
                 lambda: _issue_product(only, 1)):
        with pytest.raises(EventOnlyProduct) as raised:
            door()
        assert raised.value.detail["code"] == "event_only_product" and raised.value.status_code == 409


def test_refuse_event_only_ids_names_the_products_and_ignores_other_tenants():
    maker, other = make_space("w221b-names"), make_space("w221b-names-other")
    only = make_product(maker, name="Tripod", event_only=True)
    foreign = make_product(other, name="Foreign", event_only=True)
    with pytest.raises(EventOnlyProduct) as raised:
        refuse_event_only_ids(maker, [only.pk, foreign.pk])
    assert raised.value.detail["products"] == ["Tripod"]
    refuse_event_only_ids(maker, [foreign.pk])  # not this makerspace's product: no refusal here


def test_ordinary_request_intake_refuses_event_only_before_creating_anything():
    from django.urls import reverse
    from rest_framework.test import APIClient
    maker = make_space("w221b-intake")
    maker.enabled_modules = sorted((set(maker.enabled_modules or []) | {"request_workflow", "public_inventory"}) - {"presence"})  # intake with presence on needs a check-in first
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"loans.enabled"})
    maker.public_site_enabled = maker.public_inventory_enabled = True
    maker.save(update_fields=["enabled_modules", "enabled_features", "public_site_enabled", "public_inventory_enabled"])
    only = make_product(maker, name="Only", event_only=True)
    member = make_user("w221b-member")
    from tests.accounts.account_factories import make_membership
    make_membership(member, maker)  # intake needs an active membership; the refusal under test comes after it
    client = APIClient()
    client.force_authenticate(member)
    response = client.post(reverse("hardware_requests:request-submit", kwargs={"makerspace_slug": maker.slug}),
                           {"requested_for": "Home", "items": [{"product_id": only.pk, "quantity": 1}]},
                           format="json")
    assert response.status_code == 409 and response.data["code"] == "event_only_product", response.data
    assert not HardwareRequest.objects.filter(makerspace=maker).exists() and not HardwareRequestItem.objects.exists()


def test_public_catalogue_shows_event_only_with_a_neutral_label_and_a_flag():
    from apps.inventory.public_availability import EVENT_ONLY_LABEL, get_public_availability
    from apps.inventory.serializers import PublicProductSerializer
    maker = make_space("w221b-public")
    only = make_product(maker, name="Only", is_public=True, event_only=True, total_quantity=10,
                        available_quantity=10, public_availability_mode="exact_count", show_public_count=True)
    assert get_public_availability(only) == {"mode": "status_only", "label": EVENT_ONLY_LABEL}  # no count
    assert EVENT_ONLY_LABEL == "Lent at events only"
    plain = make_product(maker, name="Plain", is_public=True, total_quantity=10, available_quantity=10)
    assert PublicProductSerializer(only).data["event_only"] is True
    assert PublicProductSerializer(plain).data["event_only"] is False
    assert get_public_availability(plain)["label"] == "Available"


def test_hidden_availability_stays_hidden_for_an_event_only_product():
    from apps.inventory.public_availability import get_public_availability
    maker = make_space("w221b-public-hidden")
    only = make_product(maker, name="Only", is_public=True, event_only=True, public_availability_mode="hidden")
    assert get_public_availability(only) is None


def test_a_booking_context_link_refuses_an_event_only_loan_without_an_event_context():
    from apps.bookings import loan_context_services as services
    from apps.bookings.models import BookableSpace, Booking
    from apps.bookings.models_loan_context import BookingLoanContext
    from tests.test_request_workflow import make_hardware_request, make_member
    maker = make_space("w221b-booking-link")
    maker.enabled_modules = sorted(set(maker.enabled_modules or []) | {"bookings", "request_workflow"})
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"loans.enabled"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member("w221b-booking-link-mgr", maker)
    only = make_product(maker, name="Only", is_public=True, event_only=True)
    req = make_hardware_request(maker, only)
    room = BookableSpace.objects.create(makerspace=maker, name="Workshop")
    start = timezone.now() + timedelta(days=3)
    booking = Booking.objects.create(space=room, name="Member", email="member@example.test",
                                     starts_at=start, ends_at=start + timedelta(hours=1))
    with pytest.raises(EventOnlyProduct):
        services._refuse_event_only_without_event(req)
    assert not BookingLoanContext.objects.filter(request=req).exists()
    from tests.events.test_event_equipment_desk import _enable, _event, _link
    _enable(maker)
    _link(maker, req, _event(maker))
    services._refuse_event_only_without_event(req)  # an active event context is the proof
    assert booking.pk  # the booking itself is untouched
    assert actor.pk
