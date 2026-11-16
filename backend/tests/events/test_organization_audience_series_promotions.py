"""Series audience review resumes imported queues before admitting newcomers."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events import services, services_series_update
from apps.events.models import Event, EventSeries
from apps.events.organization_audience import AUDIENCE
from apps.events.services_series import update_series
from apps.tenant_migration.row_planning import _apply_target_fields
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import direct
from tests.events.test_organization_audience_import_promotions import imported_waitlist

pytestmark = pytest.mark.django_db


def series_waitlist(capacity=1):
    event, manager, orgs, early, first, second = imported_waitlist()
    event = services.update_event(event, actor=manager, capacity=capacity)
    source = {"registration_audience": AUDIENCE, "organization_admission_blocked": False}
    target = dict(source)
    _apply_target_fields("events.EventSeries", source, target)
    series = EventSeries.objects.create(
        makerspace=event.makerspace, title="Imported series", status="published",
        recurrence_timezone="UTC", dtstart_local_date=event.starts_at.date(),
        dtstart_local_time=event.starts_at.time().replace(microsecond=0),
        recurrence_rule="FREQ=DAILY;COUNT=1", duration_minutes=120,
        capacity=capacity, **target,
    )
    event.series = series
    event.series_occurrence_key = f"1:{event.starts_at.strftime('%Y%m%dT%H%M%S')}"
    event.series_revision = series.revision
    event.save(update_fields=["series", "series_occurrence_key", "series_revision"])
    return series, event, manager, orgs, early, first, second


@pytest.mark.parametrize("capacity", [1, 0])
def test_series_review_promotes_eligible_fifo_waiters_transactionally(capacity):
    series, event, manager, orgs, early, first, second = series_waitlist(capacity)
    early_position = early.waitlist_position_at
    update_series(series, actor=manager, description="Awaiting local review")
    event.refresh_from_db()
    assert event.organization_admission_blocked
    assert not event.registrations.filter(status="registered").exists()

    response = client_for(manager).patch(
        reverse("admin-event-series-detail", args=[series.pk]),
        {"registration_audience": AUDIENCE}, format="json",
    )
    assert response.status_code == 200, response.data
    series.refresh_from_db()
    event.refresh_from_db()
    assert not series.organization_admission_blocked
    assert not event.organization_admission_blocked
    for row in (early, first, second):
        row.refresh_from_db()
    assert early.status == "waitlisted" and early.waitlist_position_at == early_position
    assert first.status == "registered"
    assert second.status == ("registered" if capacity == 0 else "waitlisted")
    promoted_ids = [first.pk, second.pk] if capacity == 0 else [first.pk]
    promotions = AuditLog.objects.filter(action="event.registration_promoted").order_by("id")
    assert [int(row.target_id) for row in promotions] == promoted_ids
    assert all(row.actor_id == manager.pk and row.meta["promotion_mode"] == "automatic_fifo"
               for row in promotions)
    newcomer = services.register(event, member=direct(orgs[0], "series-newcomer"))
    assert newcomer.status == ("registered" if capacity == 0 else "waitlisted")


def test_series_review_failure_rolls_back_marker_promotions_and_audits(monkeypatch):
    series, event, manager, _, early, first, second = series_waitlist()
    before_audits = AuditLog.objects.count()
    original = services_series_update.audit.record

    def fail_series_audit(actor, action, **kwargs):
        if action == "event.series_updated":
            assert not Event.objects.get(pk=event.pk).organization_admission_blocked
            assert event.registrations.get(pk=first.pk).status == "registered"
            raise RuntimeError("Series audit failed")
        return original(actor, action, **kwargs)

    monkeypatch.setattr(services_series_update.audit, "record", fail_series_audit)
    with pytest.raises(RuntimeError, match="Series audit failed"):
        update_series(series, actor=manager, registration_audience=AUDIENCE)
    series.refresh_from_db()
    event.refresh_from_db()
    assert series.organization_admission_blocked and event.organization_admission_blocked
    for row in (early, first, second):
        row.refresh_from_db()
        assert row.status == "waitlisted"
    assert AuditLog.objects.count() == before_audits


@pytest.mark.parametrize("guard", ["override", "draft", "approval"])
def test_series_review_preserves_occurrence_promotion_guards(guard):
    series, event, manager, _, early, first, second = series_waitlist()
    if guard == "override":
        event.series_override_fields = ["registration_audience"]
        event.save(update_fields=["series_override_fields"])
    elif guard == "draft":
        Event.objects.filter(pk=event.pk).update(status="draft")
    else:
        Event.objects.filter(pk=event.pk).update(registration_requires_approval=True)
    update_series(series, actor=manager, registration_audience=AUDIENCE)
    event.refresh_from_db()
    assert event.organization_admission_blocked == (guard == "override")
    for row in (early, first, second):
        row.refresh_from_db()
        assert row.status == "waitlisted"
    assert not AuditLog.objects.filter(action="event.registration_promoted").exists()
