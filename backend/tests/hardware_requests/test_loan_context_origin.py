"""Staff-origin scope of optional loan-context request and direct-loan routes."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.bookings.models import Booking, BookableSpace
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import PublicToolLoan
from tests.bookings.admin_api_helpers import grant
from tests.test_request_workflow import (
    authenticated_client, make_hardware_request, make_member, make_product, make_space,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("domain", ["event", "booking"])
@pytest.mark.parametrize("route_kind", ["request", "loan"])
def test_context_requires_matching_staff_origin_on_all_methods(domain, route_kind):
    target = make_space(f"origin-target-{domain}-{route_kind}")
    other = make_space(f"origin-other-{domain}-{route_kind}")
    target.enabled_modules = list(set(target.enabled_modules or []) | {"events", "bookings", "request_workflow"})
    target.enabled_features = list(set(target.enabled_features or []) | {"loans.enabled", "inventory.self_checkout"})
    for row in (target, other):
        row.frontend_domain = f"{row.slug}.example.test"
        row.frontend_domain_status = "verified"
        fields = ["frontend_domain", "frontend_domain_status"]
        if row.pk == target.pk:
            fields += ["enabled_modules", "enabled_features"]
        row.save(update_fields=fields)
    actor = make_member(f"origin-staff-{domain}-{route_kind}", target)
    grant(actor, other)
    request = make_hardware_request(target, make_product(target))
    if route_kind == "loan":
        loan = PublicToolLoan.objects.create(makerspace=target, request=request, requester=request.requester,
            source=PublicToolLoan.Source.ADMIN_DIRECT, target_type="direct", target_id=request.pk, target_label="Tool")
        subject = f"direct-loans/{loan.pk}"
    else:
        subject = f"requests/{request.pk}"
    start = timezone.now() + timedelta(days=2)
    if domain == "event":
        item = Event.objects.create(makerspace=target, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
        body = {"event_id": item.pk, "participant_registration_id": None}
        model, field = EventLoanContext, "event_id"
    else:
        room = BookableSpace.objects.create(makerspace=target, name="Room")
        item = Booking.objects.create(space=room, name="Member", email="member@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
        body = {"booking_id": item.pk}
        model, field = BookingLoanContext, "booking_id"
    url = f"/api/v1/admin/makerspace/{target.pk}/{subject}/{domain}-context"
    client = authenticated_client(actor)
    own = {"HTTP_ORIGIN": f"https://{target.frontend_domain}"}
    foreign = {"HTTP_ORIGIN": f"https://{other.frontend_domain}"}
    empty = client.get(url, **own)
    assert empty.status_code == 200 and empty.data["active"] is False
    body.update(expected_generation=empty.data["generation"], expected_revision=empty.data["revision"])
    linked = client.put(url, body, format="json", **own)
    assert linked.status_code == 200
    assert client.get(url, **foreign).status_code == 403
    body["expected_revision"] = linked.data["revision"]
    assert client.put(url, body, format="json", **foreign).status_code == 403
    cas = {"expected_generation": linked.data["generation"], "expected_revision": linked.data["revision"]}
    assert client.delete(url + f"?intended_{domain}_id={item.pk}", cas, format="json", **foreign).status_code == 403
    saved = model.objects.get(request=request)
    assert saved.active and getattr(saved, field) == item.pk and saved.revision == linked.data["revision"]
