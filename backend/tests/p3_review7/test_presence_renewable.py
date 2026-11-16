"""The current endpoint restores only the latest server-renewable expired session."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.presence import services
from apps.presence.models import PresenceSession
from apps.presence.policy import PresenceError

pytestmark = pytest.mark.django_db


def expired(lane, *, user=None, minutes=3, ended=False, reason="expired", **values):
    user = user or lane.owner
    now = timezone.now()
    return PresenceSession.objects.create(makerspace=lane.space, account=user, member=user,
        started_at=now - timedelta(hours=2), expires_at=now - timedelta(minutes=minutes),
        ended_at=now - timedelta(minutes=minutes) if ended else None,
        end_reason=reason if ended else "", **values)


def current(lane, user=None):
    return lane.client(user or lane.owner).get(f"/api/v1/public/{lane.space.slug}/presence-sessions/current")


@pytest.mark.parametrize("ended", [False, True])
def test_current_restores_expired_session_before_or_after_sweeper_and_renews(lane, ended):
    row = expired(lane, ended=ended, hide_on_display=True)
    response = current(lane)
    assert response.status_code == 200, response.data
    assert response.data["active"] is False and response.data["session"] is None
    renewable = response.data["renewable"]
    assert renewable["active"] is False and renewable["status"] == "visiting"
    assert renewable["hide_on_display"] is True and renewable["names_displayed"] is False
    assert not {"id", "account_id", "member_id", "email", "created_via_claim_session"} & set(renewable)
    assert lane.owner.email not in str(response.data)
    result = lane.client(lane.owner).post(f"/api/v1/public/{lane.space.slug}/presence-sessions/current/renew",
        {"duration_minutes": 120}, format="json")
    assert result.status_code == 200, result.data
    row.refresh_from_db()
    assert row.revision == 2 and row.ended_at is None and row.expires_at > timezone.now()
    after = current(lane).data
    assert after["active"] is True and after["renewable"] is None


@pytest.mark.parametrize("seconds,allowed", [(599, True), (600, True), (601, False)])
def test_read_and_writer_share_exact_ten_minute_boundary(lane, monkeypatch, seconds, allowed):
    now = timezone.now()
    monkeypatch.setattr("apps.presence.services.timezone.now", lambda: now)
    row = expired(lane, ended=True)
    row.expires_at = now - timedelta(seconds=seconds)
    row.save(update_fields=["expires_at"])
    assert bool(current(lane).data["renewable"]) is allowed
    if allowed:
        assert services.renew_session(lane.owner, lane.space, 60).pk == row.pk
    else:
        with pytest.raises(PresenceError):
            services.renew_session(lane.owner, lane.space, 60)


@pytest.mark.parametrize("reason", ["user_ended", "staff_ended", "superseded", "membership_revoked", "claim_revoked"])
def test_explicitly_ended_sessions_never_offer_renewal(lane, reason):
    expired(lane, ended=True, reason=reason)
    assert current(lane).data["renewable"] is None
    with pytest.raises(PresenceError):
        services.renew_session(lane.owner, lane.space, 60)


def test_only_latest_session_can_be_renewable(lane):
    old = expired(lane)
    latest = expired(lane, ended=True, reason="user_ended")
    latest.started_at = old.started_at + timedelta(minutes=1)
    latest.save(update_fields=["started_at"])
    assert current(lane).data["renewable"] is None


def test_empty_active_and_owner_tenant_scoping(lane):
    assert current(lane).data["renewable"] is None
    expired(lane, user=lane.guest)
    foreign = Makerspace.objects.create(name="Other", slug="other-renewable")
    now = timezone.now()
    PresenceSession.objects.create(makerspace=foreign, account=lane.owner, member=lane.owner,
        started_at=now - timedelta(hours=2), expires_at=now - timedelta(minutes=2))
    assert current(lane).data["renewable"] is None
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    response = current(lane).data
    assert response["active"] is True and response["renewable"] is None


@pytest.mark.parametrize("gate", ["membership", "module", "account"])
def test_current_keeps_live_access_gates(lane, gate):
    expired(lane)
    if gate == "membership":
        MakerspaceMembership.objects.filter(makerspace=lane.space, user=lane.owner).update(status="revoked")
    elif gate == "module":
        lane.space.enabled_modules.remove("presence")
        lane.space.save(update_fields=["enabled_modules"])
    else:
        lane.owner.access_status = "restricted"
        lane.owner.save(update_fields=["access_status"])
    assert current(lane).status_code in {403, 404}


@pytest.mark.parametrize("invalid", [None, "ended", "cancelled", "registration", "module"])
def test_event_deadline_and_live_authority_match_renewal(lane, invalid):
    from apps.events.models import Event, EventRegistration
    now = timezone.now()
    event = Event.objects.create(makerspace=lane.space, title="Workshop", status="published",
        starts_at=now - timedelta(hours=2), ends_at=now + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=lane.owner, status="attended",
        name="Owner", email=lane.owner.email, registered_via_makerspace=lane.space)
    expired(lane, event_registration=registration, status="attending_event")
    if invalid == "ended":
        event.ends_at = now - timedelta(minutes=1)
        event.save(update_fields=["ends_at"])
    elif invalid == "cancelled":
        event.status = "cancelled"
        event.save(update_fields=["status"])
    elif invalid == "registration":
        registration.status = "cancelled"
        registration.save(update_fields=["status"])
    elif invalid == "module":
        lane.space.enabled_modules.remove("events")
        lane.space.save(update_fields=["enabled_modules"])
    assert bool(current(lane).data["renewable"]) is (invalid is None)
    if invalid:
        with pytest.raises(PresenceError):
            services.renew_session(lane.owner, lane.space, 60)
    else:
        assert services.renew_session(lane.owner, lane.space, 120).expires_at == event.ends_at


def claim_for(lane, user):
    from apps.accounts.models_claim import MemberClaimCode
    now = timezone.now()
    return MemberClaimCode.objects.create(
        membership=user.makerspace_memberships.get(makerspace=lane.space), code_digest=uuid4().hex,
        issued_by=lane.staff, expires_at=now + timedelta(minutes=5), consumed_at=now,
        absolute_expires_at=now + timedelta(minutes=30))


@pytest.mark.parametrize("same_claim", [False, True])
def test_renewable_is_bound_to_the_authenticated_claim_session(lane, same_claim):
    from apps.accounts.claim_sessions import attach_claim_context
    user = lane.person("renew-walkin")
    user.is_walk_in = True
    user.set_unusable_password()
    user.save(update_fields=["is_walk_in", "password"])
    claim = claim_for(lane, user)
    expired(lane, user=user, created_via_claim_session=claim)
    attach_claim_context(user, claim if same_claim else claim_for(lane, user))
    assert bool(current(lane, user).data["renewable"]) is same_claim
    if same_claim:
        assert services.renew_session(user, lane.space, 60).expires_at == claim.absolute_expires_at
    else:
        with pytest.raises(PresenceError):
            services.renew_session(user, lane.space, 60)


def test_hint_does_not_authorize_a_later_renewal_after_staff_ends_it(lane):
    row = expired(lane, ended=True)
    assert current(lane).data["renewable"] is not None
    row.end_reason = "staff_ended"
    row.save(update_fields=["end_reason"])
    response = lane.client(lane.owner).post(f"/api/v1/public/{lane.space.slug}/presence-sessions/current/renew",
        {"duration_minutes": 60}, format="json")
    assert response.status_code == 400 and response.data["code"] == "session_ended"
    assert current(lane).data["renewable"] is None
