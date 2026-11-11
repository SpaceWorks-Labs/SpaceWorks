from tests.account_split_g2_helpers import grant_organization_action
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier, Event as ThreadEvent

import pytest
from django.db import close_old_connections, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events import event_authority, services_staff_grants as services
from apps.events.models import EventStaffGrant, EventStaffGrantInvite
from apps.makerspaces.models import MakerspaceMembership
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def invite_fixture(**options):
    space, manager, user, event, old_grant = grant_fixture()
    old_grant.delete()
    invite, token = services.create_invite(event, actor=manager, permissions=["check_in"], **options)
    return space, manager, user, event, invite, token


def test_invite_expiry_digest_storage_single_use_and_audit():
    _, _, user, _, invite, token = invite_fixture()
    assert timedelta(days=7) - timedelta(seconds=3) <= invite.expires_at - invite.created_at <= timedelta(days=7)
    assert len(invite.token_digest) == 64 and token not in invite.token_digest
    grant = services.redeem_invite(token, actor=user)
    assert grant.permissions == ["check_in"]
    invite.refresh_from_db()
    assert invite.redeemed_by == user and invite.redeemed_at is not None
    with pytest.raises(NotFound):
        services.redeem_invite(token, actor=user)
    assert set(AuditLog.objects.values_list("action", flat=True)) >= {
        "event.staff_grant_invited", "event.staff_grant_created", "event.staff_grant_invite_redeemed",
    }
    assert token not in str(list(AuditLog.objects.values("meta")))


@pytest.mark.parametrize("state", ["expired", "revoked", "used"])
def test_invalid_invite_states_never_create_a_grant(state):
    _, manager, user, _, invite, token = invite_fixture()
    if state == "expired":
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save(update_fields=["expires_at"])
    elif state == "revoked":
        services.revoke_invite(invite, actor=manager)
    else:
        invite.redeemed_at = timezone.now()
        invite.save(update_fields=["redeemed_at"])
    with pytest.raises(NotFound):
        services.redeem_invite(token, actor=user)
    assert not EventStaffGrant.objects.exists()


@pytest.mark.parametrize("state", ["creator_revoked", "creator_deleted", "creator_suspended", "creator_password_reset", "space_archived", "module_off"])
def test_redemption_rechecks_creator_and_tenant(state):
    space, manager, user, _, invite, token = invite_fixture()
    if state == "creator_revoked":
        # The Space Manager's authority lives on the staff-TRACK row, which the default
        # community manager does not see.
        MakerspaceMembership.staff_tracks.filter(user=manager, makerspace=space).update(status="revoked")
    elif state == "creator_deleted":
        # Audit actors are PROTECTed; a missing attribution FK is still a valid
        # retained-row state and must never delegate authority.
        EventStaffGrantInvite.objects.filter(pk=invite.pk).update(created_by=None)
    elif state == "creator_suspended":
        User.objects.filter(pk=manager.pk).update(access_status="suspended")
    elif state == "creator_password_reset":
        User.objects.filter(pk=manager.pk).update(must_change_password=True)
    elif state == "space_archived":
        space.archived_at = timezone.now()
        space.save(update_fields=["archived_at"])
    else:
        space.enabled_modules.remove("events")
        space.save(update_fields=["enabled_modules"])
    # An off module leaves no surface: SurfaceOff is a NotFound (#95).
    with pytest.raises((PermissionDenied, ValidationError, NotFound)):
        services.redeem_invite(token, actor=user)
    invite.refresh_from_db()
    assert invite.redeemed_at is None and not EventStaffGrant.objects.exists()


def test_redemption_non_escalation_survives_future_adapter_authority_narrowing(monkeypatch):
    _, _, user, _, invite, token = invite_fixture()
    # Domain management and individual permissions are independently revalidated;
    # simulate an adapter retaining management while losing this permission.
    monkeypatch.setattr(services, "ADAPTER", replace(services.ADAPTER, can=lambda *args: False))
    with pytest.raises(PermissionDenied):
        services.redeem_invite(token, actor=user)
    invite.refresh_from_db()
    assert invite.redeemed_at is None and not EventStaffGrant.objects.exists()


@pytest.mark.parametrize("email", ["mismatch", "unverified", "matching"])
def test_email_bound_invite_requires_matching_verified_email(email):
    _, _, user, _, invite, token = invite_fixture(email="EVENT-GRANTEE@example.test")
    if email == "mismatch":
        user.email = "other@example.test"
        user.save(update_fields=["email"])
    elif email == "unverified":
        user.email_verified_at = None
        user.save(update_fields=["email_verified_at"])
    if email == "matching":
        assert services.redeem_invite(token, actor=user).user == user
    else:
        with pytest.raises(PermissionDenied):
            services.redeem_invite(token, actor=user)
        invite.refresh_from_db()
        assert invite.redeemed_at is None and not EventStaffGrant.objects.exists()


def test_grant_holder_cannot_delegate_or_edit_grants_and_every_manager_write_is_audited():
    _, manager, user, event, grant = grant_fixture()
    with pytest.raises(PermissionDenied):
        services.create_invite(event, actor=user, permissions=["edit_details"])
    with pytest.raises(PermissionDenied):
        services.update_permissions(grant, actor=user, permissions=["check_in"])
    services.update_permissions(grant, actor=manager, permissions=["check_in"])
    assert event_authority.can(user, event, "check_in")
    assert not event_authority.can(user, event, "edit_details")
    services.revoke_grant(grant, actor=manager)
    assert not event_authority.can(user, event, "check_in")
    # Revocation ends the grant's manual source (role/shift sources are independent),
    # audited as the manual revocation plus the entitlement it closed.
    assert set(AuditLog.objects.values_list("action", flat=True)) >= {
        "event.staff_grant_updated", "event.staff_grant_manual_revoked", "event.entitlement.revoked",
    }


def test_invite_api_returns_token_once_and_lists_no_credentials():
    _, manager, user, event, _ = grant_fixture()
    client = client_for(manager)
    url = reverse("admin-event-staff-invites", args=[event.pk])
    response = client.post(url, {"permissions": ["check_in"], "email": user.email}, format="json")
    assert response.status_code == 201
    assert "token" in response.data
    listed = client.get(url)
    assert listed.status_code == 200
    assert response.data["token"] not in str(listed.data)
    assert not {"token_digest", "email_digest", "token"} & set(listed.data["results"][0])


def test_invitation_mail_uses_only_redacted_synchronous_delivery(monkeypatch, django_capture_on_commit_callbacks):
    _, manager, user, event, _ = grant_fixture()
    sent = []
    monkeypatch.setattr("apps.integrations.dispatch_outbox.dispatch_email", lambda **kwargs: sent.append(kwargs))
    with django_capture_on_commit_callbacks(execute=True):
        _, token = services.create_invite(
            event, actor=manager, permissions=["check_in"], email=user.email, send_email=True,
        )
    assert len(sent) == 1
    assert sent[0]["persist_body"] is False and sent[0]["sync"] is True
    assert f"#token={token}" in sent[0]["text_body"]
    assert token not in str(list(AuditLog.objects.values("meta")))


def test_invite_token_is_case_sensitive_and_wrong_tenant_is_not_found():
    space, _, user, _, invite, token = invite_fixture()
    with pytest.raises(NotFound):
        services.redeem_invite(token.swapcase(), actor=user)
    with pytest.raises(NotFound):
        services.redeem_invite(token, actor=user, makerspace_id=space.pk + 10000)
    invite.refresh_from_db()
    assert invite.redeemed_at is None


def test_authenticated_invite_redemption_is_throttled_per_account():
    _, _, user, _, _, _ = invite_fixture()
    client = client_for(user)
    url = reverse("event-staff-invite-redeem")
    for _ in range(10):
        assert client.post(url, {"token": "unknown-token-material-that-is-long-enough"}, format="json").status_code == 404
    assert client.post(url, {"token": "unknown-token-material-that-is-long-enough"}, format="json").status_code == 429


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_redeemers_have_exactly_one_winner():
    _, _, user, _, invite, token = invite_fixture()
    other = account("concurrent-redeemer")
    barrier = Barrier(2)

    def redeem(user_id):
        close_old_connections()
        try:
            actor = User.objects.get(pk=user_id)
            barrier.wait(timeout=10)
            try:
                return "won", services.redeem_invite(token, actor=actor).pk
            except NotFound:
                return "lost", None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(redeem, [user.pk, other.pk]))
    assert sorted(result[0] for result in outcomes) == ["lost", "won"]
    assert EventStaffGrant.objects.count() == 1
    invite.refresh_from_db()
    assert invite.redeemed_by_id in {user.pk, other.pk}


@pytest.mark.django_db(transaction=True)
def test_redemption_waits_for_concurrent_creator_authority_revocation(monkeypatch):
    from apps.accounts import rbac
    from apps.events.models import EventOrganizer
    from apps.organizations.models import Organization, OrganizationMembership

    _, _, user, event, _, _ = invite_fixture()
    creator = account("concurrent-organizer")
    organization = Organization.objects.create(name="Concurrent organizer", slug="concurrent-organizer")
    membership = OrganizationMembership.objects.create(
        organization=organization, user=creator, granted_actions=[rbac.Action.MANAGE_EVENTS],
    )
    EventOrganizer.objects.create(event=event, organization=organization)
    invite, token = services.create_invite(event, actor=creator, permissions=["check_in"])
    authority_locked, redemption_entered, commit_revoke = ThreadEvent(), ThreadEvent(), ThreadEvent()
    # Redemption runs inside the shared write boundary, which takes the authority
    # locks (organizations included) before the adapter runs; observe it there.
    from apps.events import services_write_boundary as boundary
    real_lock = boundary.lock_authority

    def observed_lock(actor, target):
        redemption_entered.set()
        return real_lock(actor, target)

    monkeypatch.setattr(boundary, "lock_authority", observed_lock)

    def revoke_creator():
        close_old_connections()
        try:
            with transaction.atomic():
                Organization.objects.select_for_update().get(pk=organization.pk)
                row = OrganizationMembership.objects.select_for_update().get(pk=membership.pk)
                row.granted_actions = []
                row.save(update_fields=["granted_actions"])
                authority_locked.set()
                assert commit_revoke.wait(timeout=15)
        finally:
            close_old_connections()

    def redeem():
        close_old_connections()
        try:
            with pytest.raises(PermissionDenied):
                services.redeem_invite(token, actor=User.objects.get(pk=user.pk))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revoked = pool.submit(revoke_creator)
        assert authority_locked.wait(timeout=15)
        redeemed = pool.submit(redeem)
        try:
            assert redemption_entered.wait(timeout=15)
            assert not redeemed.done()
        finally:
            commit_revoke.set()
        revoked.result(timeout=15)
        redeemed.result(timeout=15)
    invite.refresh_from_db()
    assert invite.redeemed_at is None
    assert not EventStaffGrant.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_reciprocal_cross_tenant_redemption_does_not_deadlock_creator_user_fks(monkeypatch):
    space_a, _, creator_b, event_a, old_invite, _ = invite_fixture()
    old_invite.delete()
    creator_a = account("reciprocal-creator-a")
    space_b = event_space("reciprocal-grant-space")
    grant_organization_action(space_a, creator_a, "manage_events")
    grant_organization_action(space_b, creator_b, "manage_events")
    _, token_a = services.create_invite(event_a, actor=creator_a, permissions=["check_in"])
    _, token_b = services.create_invite(open_event(space_b), actor=creator_b, permissions=["check_in"])
    both_creators_locked = Barrier(2)
    real_lock = services.ADAPTER.lock_authority

    def synchronized_lock(actor, target):
        locked = real_lock(actor, target)
        both_creators_locked.wait(timeout=10)
        return locked

    monkeypatch.setattr(services, "ADAPTER", replace(services.ADAPTER, lock_authority=synchronized_lock))

    def redeem(values):
        token, user_id = values
        close_old_connections()
        try:
            return services.redeem_invite(token, actor=User.objects.get(pk=user_id)).user_id
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, [(token_a, creator_b.pk), (token_b, creator_a.pk)]))
    assert results == [creator_b.pk, creator_a.pk]
    assert EventStaffGrant.objects.count() == 2
