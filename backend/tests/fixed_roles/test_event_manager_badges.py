"""Custom-answer badges follow EVENT authority, not tenant audit access.

The fixed Event Manager holds manage_events but not view_audit; an event staff grant
holding manage_registrations is narrower still. Both may now print a registration's own
custom answers on a badge. The render stays audited, contacts never print, and staff
without registration authority are still refused before any answer is read.
"""
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.events.models import EventRegistration
from tests.events.checkin_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db

QUESTION = {"id": "diet", "label": "Diet", "type": "short_text", "required": False, "options": []}


def _badge_event(event):
    event.custom_form = [QUESTION]
    event.badge_template = {"fields": ["name", "custom:diet"]}
    event.save(update_fields=["custom_form", "badge_template"])
    return event


def _registration(event, name, status=EventRegistration.Status.REGISTERED):
    attendee = account(name)
    return EventRegistration.objects.create(
        event=event, member=attendee, name=name, email=attendee.email, phone="555-1234",
        status=status, custom_answers={"answers": [{"id": "diet", "value": f"{name} answer"}]},
    )


@pytest.fixture
def rendered(monkeypatch):
    captured = []

    def render(template, snapshots, **kwargs):
        captured.extend(snapshots)
        return b"%PDF-1.4"

    monkeypatch.setattr("apps.events.views_badges.render_badges_pdf", render)
    return captured


def _pdf(user, event, ids, **extra):
    return client_for(user).post(
        reverse("admin-event-badges-pdf", args=[event.pk]),
        {"registration_ids": ids, **extra}, format="json",
    )


def _actor(space, slug, name):
    user = make_user(f"{space.slug}-{name}", access_status="active", account_kind="member" if slug == "member" else "staff",
                     staff_makerspace=None if slug == "member" else space)
    assign_builtin_roles(user, space, slug)
    return user


def test_event_manager_without_audit_prints_custom_answers(rendered):
    space = event_space("em-badge-manager")
    event = _badge_event(open_event(space))
    registration = _registration(event, "em-badge-guest")
    actor = _actor(space, "event_manager", "em")
    assert not rbac.can(actor, rbac.Action.VIEW_AUDIT, space.pk)

    detail = client_for(actor).get(reverse("admin-event-detail", args=[event.pk]))
    assert detail.status_code == 200
    assert detail.data["badge_sensitive_fields_allowed"] is True

    response = _pdf(actor, event, [registration.pk])

    assert response.status_code == 200, getattr(response, "data", None)
    assert response["Content-Type"] == "application/pdf"
    assert rendered[0].fields == (("Name", "em-badge-guest"), ("Diet", "em-badge-guest answer"))
    # Only this registration's own answers, and never a contact field.
    assert all("@" not in value for _label, value in rendered[0].fields)
    log = AuditLog.objects.get(actor=actor, action="event.badges_generated")
    assert log.meta["fields"] == ["name", "custom:diet"]
    assert log.meta["count"] == 1


def test_manage_registrations_grant_holder_prints_custom_answers(rendered):
    space, manager, user, event, grant = grant_fixture("check_in")
    # Authority is read from the live manual entitlement, not the grant's display column.
    set_grant_permissions(grant, ["check_in", "manage_registrations"])
    _badge_event(event)
    attended = _registration(event, "grant-badge-guest", status=EventRegistration.Status.ATTENDED)
    assert not rbac.can(user, rbac.Action.VIEW_AUDIT, space.pk)

    response = _pdf(user, event, [attended.pk], include_attended=True)

    assert response.status_code == 200, getattr(response, "data", None)
    assert rendered[0].fields[1] == ("Diet", "grant-badge-guest answer")
    assert AuditLog.objects.filter(actor=user, action="event.badges_generated").exists()


def test_check_in_only_grant_cannot_print_custom_answers(rendered):
    space, manager, user, event, grant = grant_fixture("check_in")
    _badge_event(event)
    attended = _registration(event, "checkin-badge-guest", status=EventRegistration.Status.ATTENDED)

    response = _pdf(user, event, [attended.pk], include_attended=True)

    assert response.status_code == 403
    assert rendered == []
    assert not AuditLog.objects.filter(action="event.badges_generated").exists()


@pytest.mark.parametrize("slug", ["booking_manager", "member"])
def test_unrelated_staff_cannot_print_badges(rendered, slug):
    space = event_space(f"em-badge-{slug.replace('_', '-')}")
    event = _badge_event(open_event(space))
    registration = _registration(event, f"{slug}-badge-guest")
    actor = _actor(space, slug, "other")

    assert _pdf(actor, event, [registration.pk]).status_code in (403, 404)
    assert rendered == []
    assert not AuditLog.objects.filter(action="event.badges_generated").exists()


def test_event_manager_cannot_print_another_makerspaces_badges(rendered):
    home = event_space("em-badge-home")
    foreign = event_space("em-badge-foreign")
    event = _badge_event(open_event(foreign))
    registration = _registration(event, "foreign-badge-guest")
    actor = _actor(home, "event_manager", "em")

    assert _pdf(actor, event, [registration.pk]).status_code in (403, 404)
    assert rendered == []
