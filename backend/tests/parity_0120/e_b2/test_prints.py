"""Badge print receipts: idempotent, append-only, audited without names, the monthly limit's reach."""
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import EventBadgePrint
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db


def _desk(slug, features=FEATURES):
    space, event, sm = live_event(slug, features)
    publish_badge(space, event, sm)
    _user, registration = register(space, event, "ada")
    issue_cards(event)
    return space, event, sm, registration


def _body(registration, **extra):
    return {"receipts": [{"operation_id": str(uuid4()), "registration_id": registration.pk, "stock": "a6-portrait",
                          "role": "attendee", "printed_at": timezone.now().isoformat(), **extra}]}


def test_receipts_are_idempotent_by_operation_id_and_audited_without_names():
    _space, event, sm, registration = _desk("e2-receipt")
    body = _body(registration)
    url = f"/api/v1/admin/events/{event.pk}/badges/print-receipts"
    assert client(sm).post(url, body, format="json").json() == {"recorded": 1, "duplicates": 0}
    assert client(sm).post(url, body, format="json").json() == {"recorded": 0, "duplicates": 1}
    row = EventBadgePrint.objects.get(event=event)
    assert row.card_id and row.method == "desk" and row.role == "attendee"
    assert AuditLog.objects.filter(action="event_badge.printed").count() == 1
    assert registration.name not in str(AuditLog.objects.get(action="event_badge.printed").__dict__)


def test_a_receipt_row_cannot_be_changed_or_deleted():
    _space, event, sm, registration = _desk("e2-append")
    client(sm).post(f"/api/v1/admin/events/{event.pk}/badges/print-receipts", _body(registration), format="json")
    row = EventBadgePrint.objects.get(event=event)
    with pytest.raises(ValueError):
        row.save()
    with pytest.raises(ValueError):
        row.delete()


def test_the_routes_are_404_while_the_desk_switch_is_off():
    features = tuple(feature for feature in FEATURES if feature != "events.badge_desk_print")
    _space, event, sm, registration = _desk("e2-off", features)
    assert client(sm).post(f"/api/v1/admin/events/{event.pk}/badges/print-receipts", _body(registration),
                           format="json").status_code == 404
    assert client(sm).get(f"/api/v1/admin/events/{event.pk}/badges/desk").status_code == 404


def test_another_events_registration_is_never_recorded():
    _space, event, sm, _registration = _desk("e2-scope")
    other_space, other_event, _other_sm = live_event("e2-scope-b")
    _user, foreign = register(other_space, other_event, "x")
    url = f"/api/v1/admin/events/{event.pk}/badges/print-receipts"
    assert client(sm).post(url, _body(foreign), format="json").json() == {"recorded": 0, "duplicates": 1}


def test_the_monthly_limit_refuses_an_online_print_start_but_never_receipts():
    space, event, sm, registration = _desk("e2-limit")
    space.resource_limit_overrides = {"event_badge_prints_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    receipts = f"/api/v1/admin/events/{event.pk}/badges/print-receipts"
    desk = f"/api/v1/admin/events/{event.pk}/badges/desk?registration_id={registration.pk}"
    assert client(sm).get(desk).status_code == 200  # nothing printed yet
    assert client(sm).post(receipts, _body(registration), format="json").status_code == 200
    assert client(sm).get(desk).status_code == 409  # used up: no new print start
    # An offline desk (or a late receipt) is still recorded and counted.
    assert client(sm).post(receipts, _body(registration, method="offline"), format="json").json()["recorded"] == 1
    assert EventBadgePrint.objects.filter(event=event).count() == 2


def test_a_bulk_job_records_receipts_when_queued_and_is_refused_over_the_limit():
    space, event, sm, _registration = _desk("e2-bulk")
    url = f"/api/v1/admin/events/{event.pk}/card-jobs"
    first = client(sm).post(url, {"kind": "bulk_per_person"}, format="json")
    assert first.status_code in (200, 201)
    assert EventBadgePrint.objects.filter(event=event, method="bulk").count() == 1
    space.resource_limit_overrides = {"event_badge_prints_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert client(sm).post(url, {"kind": "zip"}, format="json").status_code == 409
