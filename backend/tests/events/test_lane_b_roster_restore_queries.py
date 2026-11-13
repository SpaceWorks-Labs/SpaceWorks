"""Roster undo hints preserve history checks without queries per registration."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.services import record
from apps.events.models import EventInvite, EventPromoCode, EventRegistration
from apps.events.serializers_registration_admin import EventRegistrationAdminSerializer
from apps.events.services_registration_tools import annotate_registration_restore_history, restore_registration
from apps.operations.cancellation_restore import RestoreRefused, restore_deadline
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def roster(settings, monkeypatch):
    # Count projection queries independently of the encryption key loader.
    settings.PII_ENCRYPTION_ENABLED = False
    now = timezone.now()
    monkeypatch.setattr("apps.events.serializers_registration_admin.timezone.now", lambda: now)
    space, manager, grantee, event, _ = grant_fixture("manage_registrations")
    return space, manager, grantee, event, now


def cancelled_row(event, now, index=0, **changes):
    values = dict(
        event=event, name=f"Attendee {index}", email=f"attendee-{index}@example.test",
        phone="12345678", registration_audience="accounts", status="cancelled",
        cancelled_at=now - timedelta(minutes=1), status_before_cancel="registered",
    )
    values.update(changes)
    return EventRegistration.objects.create(**values)


def test_default_hundred_row_page_has_query_free_restore_hints(
    roster, monkeypatch, django_assert_num_queries,
):
    _, _, grantee, event, now = roster
    rows = [cancelled_row(event, now, index) for index in range(101)]
    original = EventRegistrationAdminSerializer.get_restore_until
    seen = []

    def query_free_hint(serializer, obj):
        with django_assert_num_queries(0):
            result = original(serializer, obj)
        seen.append(obj.pk)
        return result

    monkeypatch.setattr(EventRegistrationAdminSerializer, "get_restore_until", query_free_hint)
    response = client_for(grantee).get(f"/api/v1/admin/events/{event.pk}/registrations/")
    assert response.status_code == 200, response.data
    assert response.data["count"] == 101 and response.data["next"] is not None
    assert seen == [row.pk for row in rows[:100]]
    assert all(row["restore_until"] is not None for row in response.data["results"])


@pytest.mark.parametrize("page_size", [1, 100])
def test_roster_projection_and_serialization_use_one_query(roster, page_size, django_assert_num_queries):
    _, _, _, event, now = roster
    for index in range(page_size):
        cancelled_row(event, now, index)
    queryset = annotate_registration_restore_history(EventRegistration.objects.filter(event=event))
    with django_assert_num_queries(1):
        data = EventRegistrationAdminSerializer(queryset, many=True).data
    assert len(data) == page_size
    assert all(row["restore_until"] is not None for row in data)


@pytest.mark.parametrize("case,eligible", [
    ("registered", True), ("waitlisted", True), ("pending_approval", True),
    ("missing_time", False), ("missing_prior", False), ("expired", False),
    ("not_cancelled", False), ("attended_prior", False),
    ("invite_audience", False), ("current_invite_audience", False),
    ("discount", False), ("invite_fk", False), ("promo_fk", False),
    ("invite_audit", False), ("promo_audit", False),
])
def test_batched_restore_hints_match_single_row_fallback(
    roster, case, eligible, django_assert_num_queries,
):
    space, manager, _, event, now = roster
    changes = {
        "registered": {}, "waitlisted": {"status_before_cancel": "waitlisted"},
        "pending_approval": {"status_before_cancel": "pending_approval"},
        "missing_time": {"cancelled_at": None}, "missing_prior": {"status_before_cancel": ""},
        "expired": {"cancelled_at": now - timedelta(minutes=5)},
        "not_cancelled": {"status": "registered"}, "attended_prior": {"status_before_cancel": "attended"},
        "invite_audience": {"registration_audience": "invite"},
        "discount": {"discount_amount": Decimal("1.00")},
    }.get(case, {})
    if case == "current_invite_audience":
        event.registration_audience = "invite"
        event.save(update_fields=["registration_audience"])
    if case == "invite_fk":
        changes["invite"] = EventInvite.objects.create(event=event, makerspace=space, uses=1)
    if case == "promo_fk":
        changes["promo_code"] = EventPromoCode.objects.create(
            event=event, makerspace=space, percent_off=10, uses=1,
        )
    row = cancelled_row(event, now, **changes)
    if case in ("invite_audit", "promo_audit"):
        action = "event.invite_redeemed" if case == "invite_audit" else "event.promo_redeemed"
        record(manager, action, makerspace=space, target=row)
        assert row.invite_id is None and row.promo_code_id is None
    expected = restore_deadline(row) if eligible else None
    assert EventRegistrationAdminSerializer().get_restore_until(row) == expected
    projected = annotate_registration_restore_history(EventRegistration.objects.all()).get(pk=row.pk)
    with django_assert_num_queries(0):
        assert EventRegistrationAdminSerializer().get_restore_until(projected) == expected


@pytest.mark.parametrize("status", Payment.Status.values)
def test_every_historical_charge_blocks_undo_even_without_payment_visibility(roster, status):
    space, manager, grantee, event, now = roster
    row = cancelled_row(event, now)
    Payment.objects.create(
        makerspace=space, created_by=manager, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=row.pk, amount=Decimal("1.00"), currency="usd", status=status,
    )
    projected = annotate_registration_restore_history(EventRegistration.objects.all()).get(pk=row.pk)
    assert EventRegistrationAdminSerializer().get_restore_until(row) is None
    assert EventRegistrationAdminSerializer().get_restore_until(projected) is None
    response = client_for(grantee).get(f"/api/v1/admin/events/{event.pk}/registrations/")
    assert response.status_code == 200, response.data
    assert response.data["results"][0]["payment"] is None
    assert response.data["results"][0]["restore_until"] is None


def test_history_checks_ignore_other_tenants_targets_actions_and_registrations(roster):
    space, manager, grantee, event, now = roster
    clean = cancelled_row(event, now)
    consumed = cancelled_row(event, now, 1)
    charged = cancelled_row(event, now, 2)
    foreign = event_space("foreign-roster-history")
    record(manager, "event.invite_redeemed", makerspace=foreign, target=clean)
    record(manager, "event.promo_redeemed", makerspace=space, target=event)
    record(manager, "event.registration_cancelled", makerspace=space, target=clean)
    record(manager, "event.promo_redeemed", makerspace=space, target=consumed)
    Payment.objects.create(
        makerspace=space, created_by=manager, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=charged.pk, amount=Decimal("1.00"), currency="usd", status="canceled",
    )
    response = client_for(grantee).get(f"/api/v1/admin/events/{event.pk}/registrations/")
    assert response.status_code == 200, response.data
    data = {row["id"]: row for row in response.data["results"]}
    assert data[clean.pk]["restore_until"] is not None
    assert data[consumed.pk]["restore_until"] is None
    assert data[charged.pk]["restore_until"] is None


@pytest.mark.parametrize("history,reason", [("audit", "consumed_code"), ("payment", "historical_charge")])
def test_locked_restore_rechecks_history_after_a_roster_projection(roster, history, reason):
    space, manager, _, event, now = roster
    row = cancelled_row(event, now)
    projected = annotate_registration_restore_history(EventRegistration.objects.all()).get(pk=row.pk)
    assert not projected.restore_has_consumption and not projected.restore_has_charge
    if history == "audit":
        record(manager, "event.invite_redeemed", makerspace=space, target=row)
    else:
        Payment.objects.create(
            makerspace=space, created_by=manager, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=row.pk, amount=Decimal("1.00"), currency="usd",
        )
    with pytest.raises(RestoreRefused) as failure:
        restore_registration(projected, actor=manager)
    assert str(failure.value.detail["code"]) == reason
    row.refresh_from_db()
    assert row.status == "cancelled" and row.cancelled_at == projected.cancelled_at
