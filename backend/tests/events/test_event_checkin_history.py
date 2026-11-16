"""Who has checked in, readable by a check-in-only grantee; staff role labels."""
from tests.events.manual_grant_fixture import create_manual_grant

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events import services, services_staff_grants
from apps.events.models import EventRegistration, EventStaffGrant, EventTicketType
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def url(event):
    return reverse("admin-event-check-ins", kwargs={"pk": event.pk})


def fixture():
    space = event_space("history-host")
    manager = make_staff(space)
    event = open_event(space)
    ticket = EventTicketType.objects.create(makerspace=space, event=event, name="Speaker pass")
    scanned = EventRegistration.objects.create(event=event, name="Ada Scan", email="ada@example.test", phone="1", ticket_type=ticket)
    manual = EventRegistration.objects.create(event=event, name="Bob Desk", email="bob@example.test", phone="1")
    EventRegistration.objects.create(event=event, name="Cy Waiting", email="cy@example.test", phone="1")
    services.mark_attended(scanned, actor=manager, source="qr")
    services.mark_attended(manual, actor=manager, source="online")
    return space, manager, event


def grantee(space, event, manager, permissions, name):
    user = account(name)
    create_manual_grant(makerspace=space, event=event, user=user, granted_by=manager, permissions=permissions)
    return user


def test_check_in_only_grantee_sees_a_minimal_newest_first_list():
    space, manager, event = fixture()
    speaker = grantee(space, event, manager, ["check_in"], "door-speaker")
    response = client_for(speaker).get(url(event))
    assert response.status_code == 200, response.data
    rows = response.data["results"]
    assert response.data["count"] == 2
    assert [row["attendee_name"] for row in rows] == ["Bob Desk", "Ada Scan"]
    assert set(rows[0]) == {"registration_id", "attendee_name", "ticket_type", "attended_at", "source", "checked_in_by"}
    by_name = {row["attendee_name"]: row for row in rows}
    assert by_name["Ada Scan"]["source"] == "qr" and by_name["Ada Scan"]["ticket_type"] == "Speaker pass"
    assert by_name["Bob Desk"]["source"] == "manual" and by_name["Bob Desk"]["ticket_type"] is None
    assert by_name["Bob Desk"]["checked_in_by"] == (manager.display_name or manager.username)
    assert "email" not in str(rows) and "bob@example.test" not in str(rows)


@pytest.mark.parametrize(("permissions", "status"), [
    (["edit_details"], 403), (["manage_invitations"], 403), (["manage_registrations"], 403), (["check_in"], 200),
])
def test_check_in_list_permission_matrix(permissions, status):
    space, manager, event = fixture()
    user = grantee(space, event, manager, permissions, "matrix-" + permissions[0].replace("_", "-"))
    assert client_for(user).get(url(event)).status_code == status


def test_manager_sees_list_and_other_tenants_do_not():
    space, manager, event = fixture()
    assert client_for(manager).get(url(event)).status_code == 200
    stranger = make_staff(event_space("history-other"))
    assert client_for(stranger).get(url(event)).status_code == 404
    other_event = open_event(event_space("history-third"))
    speaker = grantee(space, event, manager, ["check_in"], "scoped-speaker")
    assert client_for(speaker).get(url(other_event)).status_code == 404


def test_corrected_attendance_leaves_the_list():
    space, manager, event = fixture()
    attended = EventRegistration.objects.filter(event=event, status="attended").first()
    services.correct_attendance(attended, actor=manager)
    response = client_for(manager).get(url(event))
    assert response.data["count"] == 1


# -- Role labels ------------------------------------------------------------------------

def test_role_label_travels_from_invite_to_grant_and_is_audited():
    space = event_space("label-host")
    manager = make_staff(space)
    event = open_event(space)
    user = account("label-speaker")
    invite, token = services_staff_grants.create_invite(event, actor=manager, permissions=["check_in"], role_label="speaker")
    assert invite.role_label == "speaker"
    grant = services_staff_grants.redeem_invite(token, actor=user)
    assert grant.role_label == "speaker" and grant.permissions == ["check_in"]
    assert AuditLog.objects.filter(action="event.staff_grant_invited", meta__role_label="speaker").exists()

    updated = services_staff_grants.update_permissions(grant, actor=manager, permissions=["check_in"], role_label="volunteer")
    assert updated.role_label == "volunteer"
    unchanged = services_staff_grants.update_permissions(grant, actor=manager, permissions=["check_in", "manage_registrations"])
    assert unchanged.role_label == "volunteer"

    listed = client_for(manager).get(reverse("admin-event-staff-grants", kwargs={"pk": event.pk}))
    assert listed.status_code == 200
    assert listed.data["results"][0]["role_label"] == "volunteer"


def test_role_label_is_validated_and_patchable_over_http():
    space = event_space("label-http")
    manager = make_staff(space)
    event = open_event(space)
    user = account("label-http-user")
    grant = create_manual_grant(makerspace=space, event=event, user=user, granted_by=manager, permissions=["check_in"])
    detail = reverse("admin-event-staff-grant-detail", kwargs={"pk": grant.pk})
    bad = client_for(manager).patch(detail, {"permissions": ["check_in"], "role_label": "chief"}, format="json")
    assert bad.status_code == 400
    good = client_for(manager).patch(detail, {"permissions": ["check_in"], "role_label": "speaker"}, format="json")
    assert good.status_code == 200, good.data
    assert good.data["role_label"] == "speaker"
