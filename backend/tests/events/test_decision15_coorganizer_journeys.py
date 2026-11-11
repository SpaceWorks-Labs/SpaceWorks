"""Decision 15: a co-organizer may invite volunteers, mentors and judges with only what they hold.

A *real* co-organizer here is a person whose event authority is a live manual grant source
(``manage_team`` plus helper permissions) issued by a Space Manager through the shared invite
lifecycle. Nothing below mocks the subset validator, ``delegation_scope`` or the grant
adapter: the production policy decides every outcome. Two delegation wires exist:

* the shared staff invitation (``services_staff_grants``), event-wide by construction; and
* the programme role wire (``POST /admin/events/<id>/roles/`` then ``.../approve/``), which
  carries the helper role and its track scope.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.events import event_authority, services_staff_grants as services
from apps.events.contributions import ports as contributor_ports
from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
from apps.events.contributions.runtime import ContributorPorts
from apps.events.models import EventStaffGrant, EventStaffGrantInvite
from tests.events.collab_helpers import client_for, make_staff
from tests.events.staff_grant_helpers import set_grant_permissions
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db

CO_PERMISSIONS = ["check_in", "judge", "manage_team", "manage_volunteers", "mentor_queue"]
HELPERS = {"volunteer": ["check_in"], "mentor": ["mentor_queue"], "judge": ["judge"]}
REFUSED = (PermissionDenied, NotFound, ValidationError)


@pytest.fixture(autouse=True)
def production_ports(monkeypatch, settings):
    settings.PII_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(contributor_ports, "_adapter", ContributorPorts())


def person(name):
    return account(f"d15-{name}-{uuid4().hex[:8]}")


def granted(event, manager, permissions, name="co"):
    """Issue and redeem a real manager invitation; returns the redeemer and their grant."""
    user = person(name)
    _, token = services.create_invite(event, actor=manager, permissions=permissions)
    return user, services.redeem_invite(token, actor=user)


def world(slug="d15"):
    space = event_space(f"{slug}-{uuid4().hex[:6]}")
    space.enabled_features += ["events.volunteering", "events.mentoring", "events.hackathons"]
    space.save(update_fields=["enabled_features"])
    event = open_event(space)
    manager = make_staff(space, username=f"{slug}-manager")
    co, co_grant = granted(event, manager, CO_PERMISSIONS)
    return SimpleNamespace(space=space, event=event, manager=manager, co=co, co_grant=co_grant)


def command(client, path, version=0, **fields):
    operation = str(uuid4())
    return client.post(path, {"operation_id": operation, "expected_version": version, **fields},
                       format="json", HTTP_IDEMPOTENCY_KEY=operation)


@pytest.mark.parametrize("role", sorted(HELPERS))
def test_co_organizer_invites_each_helper_kind_with_exactly_a_held_permission(role):
    w = world()
    invite, token = services.create_invite(w.event, actor=w.co, permissions=HELPERS[role])
    assert invite.created_by == w.co and invite.permissions == HELPERS[role]
    helper = person(role)
    redeemed = client_for(helper).post(reverse("event-staff-invite-redeem"), {"token": token}, format="json")
    assert redeemed.status_code == 200, redeemed.content
    assert redeemed.data["permissions"] == HELPERS[role]
    grant = EventStaffGrant.objects.get(pk=redeemed.data["id"])
    assert grant.granted_by == w.co
    source = EventGrantEntitlement.objects.get(grant=grant, source_kind="manual", revoked_at__isnull=True)
    assert source.created_by == w.co and source.permissions == HELPERS[role]
    assert event_authority.can(helper, w.event, HELPERS[role][0])
    # The helper received the helper permission only, never the co-organizer's management.
    for other in ("manage_team", "manage_volunteers", "edit_details", *(p for p in CO_PERMISSIONS if p not in HELPERS[role])):
        assert not event_authority.can(helper, w.event, other)
    assert not event_authority.can_manage_grants(helper, w.event)


@pytest.mark.parametrize("permissions", [
    ["manage_team"],                 # delegated management escalation
    ["check_in", "manage_team"],
    ["edit_details"],                # not a helper permission at all
    ["publish_schedule"],            # a volunteer permission the co-organizer does not hold
    ["view_sponsor_track"],          # a helper role the co-organizer holds nothing for
    ["check_in", "judge"],           # no single helper role covers this mix
])
def test_co_organizer_cannot_invite_outside_their_live_helper_authority(permissions):
    w = world()
    with pytest.raises(REFUSED):
        services.create_invite(w.event, actor=w.co, permissions=permissions)
    assert not EventStaffGrantInvite.objects.filter(created_by=w.co).exists()


def test_track_scoped_or_time_boxed_source_cannot_become_an_event_wide_invitation():
    w = world()
    scoped, scoped_grant = granted(w.event, w.manager, ["judge", "manage_team"], name="scoped")
    EventGrantEntitlement.objects.filter(grant=scoped_grant, revoked_at__isnull=True).update(track_ids=[7])
    assert event_authority.can(scoped, w.event, "judge", track_id=7)
    # Decision 221(i): the invite inherits the inviter's limit instead of being event-wide.
    inherited, _ = services.create_invite(w.event, actor=scoped, permissions=["judge"])
    assert inherited.track_ids == [7]
    with pytest.raises(REFUSED):  # a different or wider track is refused
        services.create_invite(w.event, actor=scoped, permissions=["judge"], track_ids=[8])
    boxed, boxed_grant = granted(w.event, w.manager, ["judge", "manage_team"], name="boxed")
    end = timezone.now() + timedelta(hours=2)
    EventGrantEntitlement.objects.filter(grant=boxed_grant, revoked_at__isnull=True).update(valid_until=end)
    assert event_authority.can(boxed, w.event, "manage_team") and event_authority.can(boxed, w.event, "judge")
    windowed, _ = services.create_invite(w.event, actor=boxed, permissions=["judge"])
    assert windowed.valid_until == end
    with pytest.raises(REFUSED):  # a later end than the inviter's own is refused
        services.create_invite(w.event, actor=boxed, permissions=["judge"], valid_until=end + timedelta(hours=1))
    assert EventStaffGrantInvite.objects.filter(created_by__in=[scoped, boxed]).count() == 2



@pytest.mark.parametrize("change", ["co_revoked", "co_source_expired", "co_lost_permission", "invite_expired", "events_off"])
def test_redemption_rechecks_the_inviting_co_organizer_and_leaves_the_invite_unspent(change):
    w = world()
    invite, token = services.create_invite(w.event, actor=w.co, permissions=["check_in"])
    if change == "co_revoked":
        services.revoke_grant(w.co_grant, actor=w.manager)
    elif change == "co_source_expired":
        EventGrantEntitlement.objects.filter(grant=w.co_grant, revoked_at__isnull=True).update(
            valid_until=timezone.now() - timedelta(seconds=1))
    elif change == "co_lost_permission":
        set_grant_permissions(w.co_grant, ["judge", "manage_team", "mentor_queue"])
    elif change == "invite_expired":
        EventStaffGrantInvite.objects.filter(pk=invite.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    else:
        w.space.enabled_modules = [key for key in w.space.enabled_modules if key != "events"]
        w.space.save(update_fields=["enabled_modules"])
    helper = person("late")
    with pytest.raises(REFUSED):
        services.redeem_invite(token, actor=helper)
    invite.refresh_from_db()
    assert invite.redeemed_at is None and invite.redeemed_by is None
    assert not EventStaffGrant.objects.filter(user=helper).exists()


def test_helper_authority_ends_when_the_inviting_co_organizer_is_revoked():
    w = world()
    _, token = services.create_invite(w.event, actor=w.co, permissions=["check_in"])
    helper = person("door")
    services.redeem_invite(token, actor=helper)
    assert event_authority.can(helper, w.event, "check_in")
    services.revoke_grant(w.co_grant, actor=w.manager)
    assert not event_authority.can(w.co, w.event, "manage_team")
    assert not event_authority.can(helper, w.event, "check_in")


def test_update_and_revoke_check_the_old_scope_as_well_as_the_new_one():
    w = world()
    broad, broad_grant = granted(w.event, w.manager, ["check_in", "publish_schedule"], name="broad")
    # Narrowing a broader helper grant would remove publish_schedule, which the co-organizer lacks.
    with pytest.raises(PermissionDenied):
        services.update_permissions(broad_grant, actor=w.co, permissions=["check_in"])
    with pytest.raises(PermissionDenied):
        services.revoke_grant(broad_grant, actor=w.co)
    assert event_authority.can(broad, w.event, "publish_schedule")
    # A grant inside the co-organizer's own authority is theirs to end.
    own, own_grant = granted(w.event, w.manager, ["check_in"], name="own")
    services.revoke_grant(own_grant, actor=w.co)
    assert not event_authority.can(own, w.event, "check_in")
    assert event_authority.can(broad, w.event, "check_in")


def test_co_organizer_cannot_delegate_into_another_tenants_event():
    w = world()
    other = world("d15-other")
    with pytest.raises(REFUSED):
        services.create_invite(other.event, actor=w.co, permissions=["check_in"])
    assert not EventStaffGrantInvite.objects.filter(event=other.event, created_by=w.co).exists()


@pytest.mark.parametrize("role", sorted(HELPERS))
def test_programme_role_wire_lets_a_co_organizer_appoint_each_helper_kind(role):
    w = world()
    helper = person(f"role-{role}")
    client = client_for(w.co)
    base = f"/api/v1/admin/events/{w.event.pk}/roles/"
    extra = {"delegated_permissions": HELPERS[role]} if role == "volunteer" else {}
    proposed = command(client, base, member_id=helper.pk, role=role, **extra)
    assert proposed.status_code == 201, proposed.content
    assert proposed.data["state"] == "proposed"
    approved = command(client, f"{base}{proposed.data['id']}/approve/", proposed.data["version"])
    assert approved.status_code == 200, approved.content
    assert approved.data["state"] == "approved"
    source = EventGrantEntitlement.objects.get(role_assignment_id=proposed.data["id"], revoked_at__isnull=True)
    assert source.created_by == w.co and source.permissions == HELPERS[role]
    assert event_authority.can(helper, w.event, HELPERS[role][0])
    assert not event_authority.can(helper, w.event, "manage_team")


def test_programme_role_wire_refuses_permissions_or_roles_the_co_organizer_does_not_hold():
    w = world()
    narrow, _ = granted(w.event, w.manager, ["check_in", "manage_team"], name="narrow")
    client, base = client_for(narrow), f"/api/v1/admin/events/{w.event.pk}/roles/"
    judge = person("unheld-judge")
    proposed = command(client, base, member_id=judge.pk, role="judge")
    assert proposed.status_code == 201, proposed.content
    refused = command(client, f"{base}{proposed.data['id']}/approve/", proposed.data["version"])
    assert refused.status_code == 403 and refused.data["code"] == "permission_subset", refused.content
    assert EventRoleAssignment.objects.get(pk=proposed.data["id"]).state == "proposed"
    assert not EventGrantEntitlement.objects.filter(role_assignment_id=proposed.data["id"]).exists()
    assert not event_authority.can(judge, w.event, "judge")
    # A co-organizer can never appoint another co-organizer (full manager authority only).
    escalation = command(client, base, member_id=person("second-co").pk, role="co_organizer")
    assert escalation.status_code == 403, escalation.content
    # Without manage_volunteers, a volunteer appointment cannot be approved either.
    volunteer = command(client, base, member_id=person("vol").pk, role="volunteer", delegated_permissions=["check_in"])
    assert volunteer.status_code == 201, volunteer.content
    assert command(client, f"{base}{volunteer.data['id']}/approve/", volunteer.data["version"]).status_code == 403


def test_appointed_judge_authority_follows_the_hackathons_switch():
    w = world()
    judge = person("switch-judge")
    client, base = client_for(w.co), f"/api/v1/admin/events/{w.event.pk}/roles/"
    proposed = command(client, base, member_id=judge.pk, role="judge")
    assert command(client, f"{base}{proposed.data['id']}/approve/", proposed.data["version"]).status_code == 200
    assert event_authority.can(judge, w.event, "judge")
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "events.hackathons"]
    w.space.save(update_fields=["enabled_features"])
    assert not event_authority.can(judge, w.event, "judge")
    w.space.enabled_features += ["events.hackathons"]
    w.space.save(update_fields=["enabled_features"])
    assert event_authority.can(judge, w.event, "judge")


def test_co_organizer_can_issue_a_helper_invitation_over_http():
    w = world()
    url = reverse("admin-event-staff-invites", args=[w.event.pk])
    response = client_for(w.co).post(url, {"permissions": ["check_in"]}, format="json")
    assert response.status_code == 201, response.content
    assert response.data["permissions"] == ["check_in"] and response.data["token"]
    invite = EventStaffGrantInvite.objects.get(pk=response.data["id"])
    assert invite.created_by == w.co and invite.event == w.event
