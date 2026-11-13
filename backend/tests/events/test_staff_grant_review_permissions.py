"""Independent roster and schedule authority at the real staff API boundaries."""

from tests.account_split_g2_helpers import grant_organization_action

from datetime import timedelta

import pytest
from django.urls import reverse

from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import EventRegistration, EventStaffGrant
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
from tests.events.test_staff_grant_series_matrix import series_fixture
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db

QUESTION = {"id": "diet", "label": "Diet", "type": "short_text", "required": False, "options": []}


@pytest.mark.parametrize("selector", ["email", "phone", "custom:diet"])
@pytest.mark.parametrize("roster_authority", [False, True])
@pytest.mark.parametrize("audit_authority", [False, True])
def test_saved_sensitive_badges_require_roster_authority(monkeypatch, selector, roster_authority, audit_authority):
    space, manager, user, event, grant = grant_fixture("check_in")
    set_grant_permissions(grant, ["check_in", "edit_details", *(["manage_registrations"] if roster_authority else [])])
    if audit_authority:
        from tests.fixed_roles.helpers import assign_builtin_roles
        grant_organization_action(space, user, "view_audit")
    event.custom_form = [QUESTION]
    event.save(update_fields=["custom_form"])
    attendee = account("badge-attendee")
    registration = EventRegistration.objects.create(
        event=event, member=attendee, name="Attendee", email=attendee.email, phone="555-1234",
        custom_answers={"answers": [{"id": "diet", "value": "Private answer"}]},
    )
    services.mark_attended(registration, actor=manager)
    client = client_for(user)
    saved = client.put(reverse("admin-event-badge-template", args=[event.pk]), {
        "fields": ["name", selector],
    }, format="json")
    if selector in {"email", "phone"}:
        # Lane E intentionally bans contacts regardless of roster/audit authority.
        assert saved.status_code == 400, saved.data
        assert not AuditLog.objects.filter(action="event.badge_template_updated").exists()
        return
    assert saved.status_code == 200, saved.data
    rendered = []

    def render(template, snapshots, **kwargs):
        rendered.extend(snapshots)
        return b"%PDF-1.4"

    monkeypatch.setattr("apps.events.views_badges.render_badges_pdf", render)
    response = client.post(reverse("admin-event-badges-pdf", args=[event.pk]), {
        "registration_ids": [registration.pk],
    }, format="json")
    # Event-scoped: the manage_registrations grant alone admits custom answers; tenant
    # VIEW_AUDIT neither adds nor is required.
    if roster_authority:
        assert response.status_code == 200
        assert rendered[0].fields[1][1] == "Private answer"
    else:
        assert response.status_code == 403
        assert rendered == []
        assert not AuditLog.objects.filter(action="event.badges_generated").exists()


def test_check_in_only_can_print_safe_saved_badges(monkeypatch):
    _, manager, user, event, _ = grant_fixture("check_in")
    registration = EventRegistration.objects.create(event=event, member=account("safe-badge"), name="Safe name")
    services.mark_attended(registration, actor=manager)
    rendered = []

    def render(template, snapshots, **kwargs):
        rendered.extend(snapshots)
        return b"%PDF-1.4"

    monkeypatch.setattr("apps.events.views_badges.render_badges_pdf", render)
    response = client_for(user).post(reverse("admin-event-badges-pdf", args=[event.pk]), {
        "registration_ids": [registration.pk],
    }, format="json")
    assert response.status_code == 200
    assert rendered[0].fields[0] == ("Name", "Safe name")


@pytest.mark.parametrize("held", ["edit_details", "publish_schedule"])
@pytest.mark.parametrize("field", ["starts_at", "ends_at"])
@pytest.mark.parametrize("inherited", [False, True])
def test_occurrence_time_edits_require_schedule_authority(held, field, inherited):
    manager, user, series = series_fixture(held)
    event = series.occurrences.get()
    # Make the inherited value observably different, while retaining a valid interval.
    services.update_event(event, actor=manager,
                          starts_at=event.starts_at + timedelta(minutes=10),
                          ends_at=event.ends_at + timedelta(minutes=10))
    event.refresh_from_db()
    before = getattr(event, field)
    expected = getattr(series.occurrences.get(), field) + timedelta(minutes=-5 if field == "starts_at" else 5)
    data = {"inherit_fields": [field]} if inherited else {field: expected.isoformat()}
    response = client_for(user).patch(reverse("admin-event-detail", args=[event.pk]), data, format="json")
    event.refresh_from_db()
    if held == "edit_details":
        assert response.status_code == 403
        assert getattr(event, field) == before
    else:
        assert response.status_code == 200, response.data
        assert getattr(event, field) != before
        assert (field not in event.series_override_fields) if inherited else (field in event.series_override_fields)


@pytest.mark.parametrize("held", ["edit_details", "publish_schedule"])
def test_mixed_occurrence_details_and_times_require_both_permissions(held):
    _, user, series = series_fixture(held)
    event = series.occurrences.get()
    response = client_for(user).patch(reverse("admin-event-detail", args=[event.pk]), {
        "title": "Mixed edit", "ends_at": (event.ends_at + timedelta(minutes=5)).isoformat(),
    }, format="json")
    assert response.status_code == 403
    original = event.ends_at
    event.refresh_from_db()
    assert event.title != "Mixed edit" and event.ends_at == original


def test_combined_grant_can_change_occurrence_details_and_times():
    _, user, series = series_fixture("edit_details")
    grant = EventStaffGrant.objects.get(series=series, user=user)
    set_grant_permissions(grant, [*grant.permissions, "publish_schedule"])
    event = series.occurrences.get()
    expected = event.ends_at + timedelta(minutes=5)
    response = client_for(user).patch(reverse("admin-event-detail", args=[event.pk]), {
        "title": "Mixed edit", "ends_at": expected.isoformat(),
    }, format="json")
    assert response.status_code == 200, response.data
    event.refresh_from_db()
    assert event.title == "Mixed edit" and event.ends_at == expected
