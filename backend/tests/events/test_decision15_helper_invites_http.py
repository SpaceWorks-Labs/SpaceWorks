"""Decision 15 over HTTP: the shared staff-invite routes admit a co-organizer holding manage_team.

The co-organizer is a real redeemed manual grant (no mocked validator). Lists are narrowed to the
rows they issued; every write is still decided by the grant adapter's subset validator.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events import event_authority, services_staff_grants as services
from apps.events.contributions import ports as contributor_ports
from apps.events.contributions.runtime import ContributorPorts
from apps.events.models import EventStaffGrantInvite
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db

CO_PERMISSIONS = ["check_in", "judge", "manage_team", "manage_volunteers", "mentor_queue"]


@pytest.fixture(autouse=True)
def production_ports(monkeypatch, settings):
    settings.PII_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(contributor_ports, "_adapter", ContributorPorts())


def person(name):
    return account(f"d15h-{name}-{uuid4().hex[:8]}")


def granted(event, manager, permissions, name="co"):
    user = person(name)
    _, token = services.create_invite(event, actor=manager, permissions=permissions)
    return user, services.redeem_invite(token, actor=user)


def world(slug="d15h"):
    space = event_space(f"{slug}-{uuid4().hex[:6]}")
    space.enabled_features += ["events.volunteering", "events.mentoring", "events.hackathons"]
    space.save(update_fields=["enabled_features"])
    event = open_event(space)
    manager = make_staff(space, username=f"{slug}-manager-{uuid4().hex[:6]}")
    co, co_grant = granted(event, manager, CO_PERMISSIONS)
    return SimpleNamespace(space=space, event=event, manager=manager, co=co, co_grant=co_grant)


def invites_url(event):
    return reverse("admin-event-staff-invites", args=[event.pk])


def grants_url(event):
    return reverse("admin-event-staff-grants", args=[event.pk])


def ids(response):
    assert response.status_code == 200, response.content
    return {row["id"] for row in response.data["results"]}


def test_co_organizer_lists_only_the_rows_they_issued_and_managers_still_see_everything():
    w = world()
    co_client = client_for(w.co)
    own = co_client.post(invites_url(w.event), {"permissions": ["mentor_queue"]}, format="json")
    assert own.status_code == 201, own.content
    helper = person("helper")
    helper_grant = services.redeem_invite(own.data["token"], actor=helper)
    pending = co_client.post(invites_url(w.event), {"permissions": ["judge"]}, format="json")
    assert pending.status_code == 201, pending.content
    manager_invite, _ = services.create_invite(w.event, actor=w.manager, permissions=["edit_details"])

    assert ids(co_client.get(invites_url(w.event))) == {own.data["id"], pending.data["id"]}
    # The co-organizer's own grant and every manager-issued grant stay out of their list.
    assert ids(co_client.get(grants_url(w.event))) == {helper_grant.pk}

    manager_client = client_for(w.manager)
    assert ids(manager_client.get(invites_url(w.event))) >= {own.data["id"], pending.data["id"], manager_invite.pk}
    assert ids(manager_client.get(grants_url(w.event))) >= {helper_grant.pk, w.co_grant.pk}


@pytest.mark.parametrize("permissions", [
    ["publish_schedule"],      # a helper permission the co-organizer does not hold
    ["manage_team"],           # delegated management escalation
    ["edit_details"],          # not a helper permission
    ["check_in", "judge"],     # no single helper role covers the mix
])
def test_co_organizer_cannot_invite_permissions_outside_their_authority_over_http(permissions):
    w = world()
    response = client_for(w.co).post(invites_url(w.event), {"permissions": permissions}, format="json")
    assert response.status_code == 403, response.content
    assert not EventStaffGrantInvite.objects.filter(created_by=w.co).exists()


def test_grant_holder_without_manage_team_is_refused_the_invite_routes():
    w = world()
    helper, _ = granted(w.event, w.manager, ["check_in", "judge"], name="no-team")
    client = client_for(helper)
    assert client.post(invites_url(w.event), {"permissions": ["check_in"]}, format="json").status_code == 403
    assert client.get(invites_url(w.event)).status_code == 403
    assert client.get(grants_url(w.event)).status_code == 403
    assert not EventStaffGrantInvite.objects.filter(created_by=helper).exists()


def test_other_tenants_event_is_not_found_for_a_co_organizer():
    w = world()
    other = world("d15h-other")
    client = client_for(w.co)
    assert client.post(invites_url(other.event), {"permissions": ["check_in"]}, format="json").status_code == 404
    assert client.get(invites_url(other.event)).status_code == 404
    assert not EventStaffGrantInvite.objects.filter(event=other.event, created_by=w.co).exists()


def test_co_organizer_revokes_their_own_helper_over_http_but_never_a_broader_grant():
    w = world()
    client = client_for(w.co)
    invite = client.post(invites_url(w.event), {"permissions": ["check_in"]}, format="json")
    assert invite.status_code == 201, invite.content
    revoked = client.post(reverse("admin-event-staff-invite-revoke", args=[invite.data["id"]]), {}, format="json")
    assert revoked.status_code == 200, revoked.content
    assert revoked.data["revoked_at"] is not None
    assert set(AuditLog.objects.filter(actor=w.co).values_list("action", flat=True)) >= {
        "event.staff_grant_invited", "event.staff_grant_invite_revoked",
    }

    broad, broad_grant = granted(w.event, w.manager, ["check_in", "publish_schedule"], name="broad")
    detail = reverse("admin-event-staff-grant-detail", args=[broad_grant.pk])
    assert client.patch(detail, {"permissions": ["check_in"]}, format="json").status_code == 403
    assert client.post(reverse("admin-event-staff-grant-revoke", args=[broad_grant.pk]), {}, format="json").status_code == 403
    assert event_authority.can(broad, w.event, "publish_schedule")
