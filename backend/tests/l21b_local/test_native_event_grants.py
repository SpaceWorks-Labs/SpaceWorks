"""#173 native event-role grants: issued behind MFA, limited to ONE event's programme routes, never staff.

The route-gate tests walk every catalogued programme route: an event grant is admitted only to the
delegable, event-targeted routes of its own event; every other route is left to the member-grant rules,
which refuse delegated and staff routes. Member grants never widen.
"""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIClient

from apps.accounts import native_event_grants as gate
from apps.accounts.delegated_routes import DELEGABLE, ROUTE_CLASSES, route_class
from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS, NATIVE_WEB_ONLY

EVENT_ROUTES = sorted(name for name, (_methods, kind) in BY_NAME.items()
                      if kind == "event" and route_class(name) == DELEGABLE and name not in NATIVE_WEB_ONLY)


def _request(name, pk, headers=None):
    return SimpleNamespace(resolver_match=SimpleNamespace(url_name=name, kwargs={"pk": pk}), headers=headers or {})


EVENT_GRANT = SimpleNamespace(authority="event", event_id=7)
MEMBER_GRANT = SimpleNamespace(authority="member", event_id=None)
STAFF_GRANT = SimpleNamespace(authority="staff", event_id=None)
VERIFIED = {"mfa_source": "verified"}


def test_there_are_event_desk_routes_to_open():
    assert len(EVENT_ROUTES) > 50
    for name in ("events-programme-admin-judge-assignments-score", "events-programme-admin-crew",
                 "events-programme-admin-application-stage-review-submit",
                 "events-programme-admin-judging-rounds-next-project"):
        assert name in EVENT_ROUTES


@pytest.mark.parametrize("name", EVENT_ROUTES)
def test_event_grant_reaches_every_delegable_programme_route_of_its_own_event(name):
    assert gate.admits_event_route(None, VERIFIED, _request(name, 7), name, EVENT_GRANT) is True


@pytest.mark.parametrize("name", EVENT_ROUTES)
def test_event_grant_never_reaches_another_event(name):
    with pytest.raises(PermissionDenied):
        gate.admits_event_route(None, VERIFIED, _request(name, 8), name, EVENT_GRANT)


@pytest.mark.parametrize("name", EVENT_ROUTES)
def test_member_and_staff_grants_are_never_admitted_by_the_event_gate(name):
    assert gate.admits_event_route(None, VERIFIED, _request(name, 7), name, MEMBER_GRANT) is False
    assert gate.admits_event_route(None, VERIFIED, _request(name, 7), name, STAFF_GRANT) is False
    assert gate.admits_event_route(None, VERIFIED, _request(name, 7), name, None) is False


@pytest.mark.parametrize("name", sorted(set(ROUTE_CLASSES) - set(EVENT_ROUTES)))
def test_event_grant_is_not_admitted_to_any_other_classified_route(name):
    # Staff, tenant, account, series and web-only routes fall through to the member-grant rules.
    assert gate.admits_event_route(None, VERIFIED, _request(name, 7), name, EVENT_GRANT) is False


def test_event_route_needs_verified_mfa_and_no_makerspace_selection():
    name = EVENT_ROUTES[0]
    with pytest.raises(PermissionDenied):
        gate.admits_event_route(None, {"mfa_source": "password"}, _request(name, 7), name, EVENT_GRANT)
    with pytest.raises(PermissionDenied):
        gate.admits_event_route(None, VERIFIED, _request(name, 7, {"X-Makerspace-Id": "1"}), name, EVENT_GRANT)


def test_native_decisions_open_the_desks_except_the_cross_event_review_list():
    assert NATIVE_WEB_ONLY == frozenset({"events-programme-admin-my-application-reviews"})
    for name in ("events-programme-admin-crew", "events-programme-admin-crew-catering", "events-programme-admin-crew-decide",
                 "events-programme-admin-crew-remove", "events-programme-admin-application-stage-my-reviews",
                 "events-programme-admin-application-stage-review-submit"):
        assert NATIVE_DECISIONS[name] == "native"
    from apps.accounts.programme_route_catalog_l21b import L21B_ROUTES
    assert all(NATIVE_DECISIONS[name] == "native" for name, _methods, _kind in L21B_ROUTES)


def test_session_authority_names_each_grant_kind():
    assert gate.session_authority_for(EVENT_GRANT) == "native_event"
    assert gate.session_authority_for(STAFF_GRANT) == "native_staff"
    assert gate.session_authority_for(MEMBER_GRANT) == "member"


# ----- database: issuance, the payload, the HTTP gate and revocation -----

def _world(slug):
    from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
    from apps.events.models import EventStaffGrant
    from tests.events.collab_helpers import make_event, make_member, make_space, make_staff
    space = make_space(slug)
    space.enabled_features = ["events.hackathons"]
    space.save(update_fields=["enabled_features"])
    event, other = make_event(space, title="Build night"), make_event(space, title="Other night")
    manager = make_staff(space)
    from apps.events.hackathons.admission_models import HackathonConfig
    HackathonConfig.objects.create(event=event, enabled=True)
    judge = make_member(space, f"{slug}-judge")
    role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=judge, role="judge",
                                              state="approved", approved_by=manager)
    grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=judge, granted_by=manager,
                                           permissions=["judge"])
    entitlement = EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant, source_kind="manual",
                                                       permissions=["judge"], created_by=manager)
    return SimpleNamespace(space=space, event=event, other=other, manager=manager, judge=judge, role=role,
                           grant=grant, entitlement=entitlement)


def _event_grant(user, event):
    from apps.accounts.models_mfa import UserMFA
    from django.utils import timezone
    from tests.accounts.account_factories import device_grant
    UserMFA.objects.get_or_create(user=user, defaults={"enabled_at": timezone.now()})
    return device_grant(user, authority="event", event_id=event.pk, login_method="password")


def _client(user, grant):
    from apps.accounts.services_device_tokens import issue_device_token_pair
    from tests.accounts.mfa_helpers import enrolled
    row, _secret = enrolled(user)
    user._mfa_verified_version = str(row.version)
    access, _refresh, _family = issue_device_token_pair(user, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.mark.django_db
def test_step_up_requires_an_active_event_role_and_a_verified_factor(monkeypatch):
    from apps.accounts import mfa_policy
    from apps.accounts.services_device_grants import authority_for_login
    w = _world("ng-issue")
    monkeypatch.setattr(mfa_policy, "source_for", lambda user: mfa_policy.VERIFIED)
    assert authority_for_login(w.judge, login_method="password", event_id=w.event.pk) == "event"
    with pytest.raises(AuthenticationFailed):
        authority_for_login(w.judge, login_method="password", event_id=w.other.pk)
    monkeypatch.setattr(mfa_policy, "source_for", lambda user: "password")
    with pytest.raises(AuthenticationFailed):
        authority_for_login(w.judge, login_method="password", event_id=w.event.pk)


@pytest.mark.django_db
def test_event_grant_reaches_its_event_desk_and_nothing_staff():
    w = _world("ng-http")
    client = _client(w.judge, _event_grant(w.judge, w.event))
    own = client.get(f"/api/v1/admin/events/{w.event.pk}/judge-assignments/")
    assert own.status_code == 200
    assert client.get(f"/api/v1/admin/events/{w.other.pk}/judge-assignments/").status_code == 403
    assert client.get(f"/api/v1/admin/makerspaces/{w.space.pk}/security-settings").status_code == 403
    assert client.get(f"/api/v1/admin/events/{w.event.pk}/judge-assignments/",
                      HTTP_X_MAKERSPACE_ID=str(w.space.pk)).status_code == 403
    me = client.get("/api/v1/auth/me").json()
    assert me["session_authority"] == "native_event" and me["staff_roles"] == []
    assert [entry["event_id"] for entry in me["event_grants"]] == [w.event.pk]


@pytest.mark.django_db
def test_member_grant_still_refuses_the_desk_but_lists_where_to_step_up():
    from tests.accounts.account_factories import device_grant
    w = _world("ng-member")
    client = _client(w.judge, device_grant(w.judge))
    assert client.get(f"/api/v1/admin/events/{w.event.pk}/judge-assignments/").status_code == 403
    me = client.get("/api/v1/auth/me").json()
    assert me["session_authority"] == "member"
    assert [entry["event_id"] for entry in me["event_grants"]] == [w.event.pk]


@pytest.mark.django_db
def test_event_grant_is_revoked_when_the_role_ends(django_capture_on_commit_callbacks):
    from django.utils import timezone
    from apps.accounts.models_devices import DeviceGrant
    from apps.audit.models import AuditLog
    w = _world("ng-revoke")
    grant = _event_grant(w.judge, w.event)
    client = _client(w.judge, grant)
    with django_capture_on_commit_callbacks(execute=True):
        w.grant.revoked_at = timezone.now()
        w.grant.save()
    grant.refresh_from_db()
    assert grant.status == DeviceGrant.Status.REVOKED
    assert client.get(f"/api/v1/admin/events/{w.event.pk}/judge-assignments/").status_code == 401
    assert AuditLog.objects.filter(action="auth.event_grant_revoked").exists()


@pytest.mark.django_db
def test_lost_role_is_also_caught_on_the_next_request_without_a_signal():
    from apps.accounts.models_devices import DeviceGrant
    from apps.events.models import EventStaffGrant
    from django.utils import timezone
    w = _world("ng-bulk")
    grant = _event_grant(w.judge, w.event)
    client = _client(w.judge, grant)
    EventStaffGrant.objects.filter(pk=w.grant.pk).update(revoked_at=timezone.now())  # no signal fires
    assert client.get(f"/api/v1/admin/events/{w.event.pk}/judge-assignments/").status_code == 401
    grant.refresh_from_db()
    assert grant.status == DeviceGrant.Status.REVOKED


@pytest.mark.django_db
def test_database_refuses_an_event_grant_without_its_event_or_a_factor():
    from django.db import IntegrityError, transaction
    from tests.accounts.account_factories import device_grant
    w = _world("ng-db")
    with pytest.raises(IntegrityError), transaction.atomic():
        device_grant(w.judge, authority="event", event_id=w.event.pk, login_method="password")  # no factor yet
    with pytest.raises(IntegrityError), transaction.atomic():
        device_grant(w.judge, authority="event", event_id=None, login_method="password")
    with pytest.raises(IntegrityError), transaction.atomic():
        device_grant(w.judge, authority="member", event_id=w.event.pk)


def test_native_member_grant_may_redeem_an_event_staff_invite():
    from apps.accounts.surface_policy import _NATIVE_MEMBER_REFUSED
    assert "event-staff-invite-redeem" not in _NATIVE_MEMBER_REFUSED
    assert "booking-staff-invite-redeem" in _NATIVE_MEMBER_REFUSED
