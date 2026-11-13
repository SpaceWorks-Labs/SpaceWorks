"""Explicit local audience review resumes imported waitlists atomically."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events import services, services_event_details
from apps.events.models import Event
from apps.events.organization_audience import AUDIENCE
from apps.organizations.models import OrganizationMembership
from apps.tenant_migration.row_planning import _apply_target_fields
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import audience_fixture, direct

pytestmark = pytest.mark.django_db


def imported_waitlist():
    _, orgs, _, event, manager = audience_fixture(capacity=1)
    incumbent = services.register(event, member=direct(orgs[0], "incumbent"))
    early_user = direct(orgs[0], "ineligible-waiter")
    early = services.register(event, member=early_user)
    first = services.register(event, member=direct(orgs[1], "first-eligible"))
    second = services.register(event, member=direct(orgs[2], "second-eligible"))
    assert [row.status for row in (incumbent, early, first, second)] == [
        "registered", "waitlisted", "waitlisted", "waitlisted",
    ]
    # Use the portable-import projection with a target-local organization graph.
    source = {"registration_audience": AUDIENCE, "organization_admission_blocked": False}
    target = dict(source)
    _apply_target_fields("events.Event", source, target)
    Event.objects.filter(pk=event.pk).update(**target)
    event.refresh_from_db()
    assert event.organization_admission_blocked
    OrganizationMembership.objects.filter(user=early_user).update(status="suspended")
    services.cancel_registration(incumbent, actor=manager)
    for row in (early, first, second):
        row.refresh_from_db()
        assert row.status == "waitlisted"
    return event, manager, orgs, early, first, second


@pytest.mark.parametrize("capacity", [1, 0])
def test_audience_confirmation_promotes_eligible_fifo_waiters_before_new_admission(capacity):
    event, manager, orgs, early, first, second = imported_waitlist()
    early_position = early.waitlist_position_at
    # An ordinary edit, even one adding unlimited capacity, cannot resume admission.
    event = services.update_event(event, actor=manager, capacity=capacity, description="Local review pending")
    assert event.organization_admission_blocked
    assert event.registrations.filter(status="registered").count() == 0
    assert not AuditLog.objects.filter(action="event.registration_promoted").exists()

    response = client_for(manager).patch(
        reverse("admin-event-detail", args=[event.pk]),
        {"registration_audience": AUDIENCE}, format="json",
    )
    assert response.status_code == 200, response.data
    event.refresh_from_db()
    assert not event.organization_admission_blocked
    for row in (early, first, second):
        row.refresh_from_db()
    assert early.status == "waitlisted" and early.waitlist_position_at == early_position
    assert first.status == "registered"
    assert second.status == ("registered" if capacity == 0 else "waitlisted")
    promoted_ids = [first.pk, second.pk] if capacity == 0 else [first.pk]
    promoted = AuditLog.objects.filter(action="event.registration_promoted").order_by("id")
    assert [int(entry.target_id) for entry in promoted] == promoted_ids
    assert all(entry.actor_id == manager.pk for entry in promoted)
    updated = AuditLog.objects.filter(action="event.updated").latest("id")
    assert updated.meta["promoted_registration_ids"] == promoted_ids
    audience_audit = AuditLog.objects.get(action="event.audience_updated")
    assert audience_audit.meta == {
        "old_audience": AUDIENCE, "new_audience": AUDIENCE,
        "organization_ids": sorted(org.pk for org in orgs),
    }
    newcomer = services.register(event, member=direct(orgs[0], "newcomer"))
    assert newcomer.status == ("registered" if capacity == 0 else "waitlisted")


def test_audience_confirmation_rolls_back_readiness_promotions_and_audits_on_failure(monkeypatch):
    event, manager, _, early, first, second = imported_waitlist()
    before_audits = AuditLog.objects.count()
    original_audit = services_event_details._audit

    def fail_updated_audit(event, actor, action, target, meta=None):
        if action == "event.updated":
            # Promotion and the readiness save have both happened inside the transaction.
            assert not Event.objects.get(pk=event.pk).organization_admission_blocked
            assert event.registrations.get(pk=first.pk).status == "registered"
            raise RuntimeError("Audience update audit failed")
        return original_audit(event, actor, action, target, meta)

    monkeypatch.setattr(services_event_details, "_audit", fail_updated_audit)
    with pytest.raises(RuntimeError, match="Audience update audit failed"):
        services.update_event(event, actor=manager, registration_audience=AUDIENCE)
    event.refresh_from_db()
    assert event.organization_admission_blocked
    for row in (early, first, second):
        row.refresh_from_db()
        assert row.status == "waitlisted"
    assert AuditLog.objects.count() == before_audits
