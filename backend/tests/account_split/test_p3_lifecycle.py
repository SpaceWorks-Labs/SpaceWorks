"""D2/D4/D6/D7 authority and transactional staff-role lifecycle.

One account per person (#63, Q9, U-B): Space Managers grant, change, revoke and restore
staff ROLES on people; they no longer create accounts, set passwords, reactivate or reset
factors (#66). Turning a whole account off is the superadmin ``disable_account`` action.
"""
import pytest
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts import staff_account_lifecycle as lifecycle, staff_account_services as service
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_assignments import set_membership_roles
from .p3_helpers import PASSWORD, client, context

pytestmark = pytest.mark.django_db(transaction=True)


def _community(space, user):
    return MakerspaceMembership.objects.create(user=user, makerspace=space, role="member",
                                               assigned_role=space.roles.get(slug="member"))


@pytest.fixture
def ctx(settings):
    ctx = context(settings)
    ctx.joiner = User.objects.create_user("p3-joiner", password=PASSWORD)
    _community(ctx.space, ctx.joiner)
    return ctx


def _snapshot():
    users = list(User.objects.order_by("pk").values_list("pk", "is_active", "password", "credential_generation"))
    rows = list(MakerspaceMembership.all_tracks.order_by("pk").values_list("pk", "status", "assigned_role_id"))
    return users, rows


@pytest.mark.parametrize("operation", ["grant", "revoke", "restore", "change"])
@pytest.mark.parametrize("actor_name", ["root", "manager", "foreign", "worker", "member"])
def test_authority_matrix(ctx, operation, actor_name):
    actor = getattr(ctx, actor_name)
    if operation == "restore":
        ctx.membership.status = "revoked"
        ctx.membership.save(update_fields=["status"])
    allowed = actor_name in ("manager", "root")

    def execute():
        if operation == "grant":
            return service.grant(actor, ctx.space.pk, user_id=ctx.joiner.pk, roles=["inventory_manager"])
        if operation == "change":
            return service.change(actor, ctx.space.pk, ctx.membership.pk, roles=["event_manager"])
        return getattr(lifecycle, operation)(actor, ctx.space.pk, ctx.membership.pk)

    if allowed:
        execute()
    else:
        before = _snapshot()
        with pytest.raises((Http404, APIException)):
            execute()
        assert _snapshot() == before


@pytest.mark.parametrize("operation", ["revoke", "restore", "change"])
def test_manager_targets_and_self_are_exclusive(ctx, operation):
    def execute(target):
        row = MakerspaceMembership.staff_tracks.get(user=target, makerspace=ctx.space)
        if operation == "change":
            return service.change(ctx.manager, ctx.space.pk, row.pk, roles=["inventory_manager"])
        return getattr(lifecycle, operation)(ctx.manager, ctx.space.pk, row.pk)

    with pytest.raises(APIException):
        execute(ctx.manager)
    if operation == "restore":
        MakerspaceMembership.staff_tracks.filter(user=ctx.peer).update(status="revoked")
    # Only the platform superadmin manages Space Managers (#110, #111 Q14).
    with pytest.raises(APIException):
        execute(ctx.peer)


def test_space_manager_grant_policy(ctx):
    row = service.grant(ctx.root, ctx.space.pk, user_id=ctx.joiner.pk, roles=["space_manager"])
    assert row.assigned_role.slug == "space_manager" and row.user_id == ctx.joiner.pk
    other = User.objects.create_user("p3-denied", password=PASSWORD)
    _community(ctx.space, other)
    with pytest.raises(APIException):
        service.grant(ctx.manager, ctx.space.pk, user_id=other.pk, roles=["space_manager"])
    assert not MakerspaceMembership.staff_tracks.filter(user=other).exists()


def test_grant_requires_a_community_member(ctx):
    with pytest.raises(APIException) as exc:
        service.grant(ctx.manager, ctx.space.pk, user_id=ctx.member.pk, roles=["inventory_manager"])
    assert exc.value.detail["code"] == "not_community_member"


def test_last_active_manager_demotion_and_revocation(ctx):
    peer_row = MakerspaceMembership.staff_tracks.get(user=ctx.peer, makerspace=ctx.space)
    manager_row = MakerspaceMembership.staff_tracks.get(user=ctx.manager, makerspace=ctx.space)
    lifecycle.revoke(ctx.root, ctx.space.pk, peer_row.pk)
    for operation in (lambda: lifecycle.revoke(ctx.root, ctx.space.pk, manager_row.pk),
                      lambda: service.change(ctx.root, ctx.space.pk, manager_row.pk, roles=["event_manager"])):
        with pytest.raises(APIException, match="last active Space Manager"):
            operation()
    manager_row.refresh_from_db()
    assert manager_row.status == "active" and manager_row.assigned_role.slug == "space_manager"


def test_disable_revokes_credentials_and_enable_does_not_restore_staff_rows(ctx):
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError
    from apps.accounts.models_reauthentication import ReauthenticationSession
    from apps.makerspaces.models_station_leases import StationOperatorLease

    refresh = str(RefreshToken.for_user(ctx.worker))
    client(ctx.worker)
    before = ctx.worker.credential_generation
    lifecycle.disable_account(ctx.root, ctx.worker.pk, reason="No longer staff")
    ctx.worker.refresh_from_db(); ctx.membership.refresh_from_db()
    assert not ctx.worker.is_active and ctx.membership.status == "revoked"
    assert ctx.membership.revocation_reason == "No longer staff"
    assert ctx.worker.credential_generation > before
    with pytest.raises(TokenError):
        RefreshToken(refresh)
    assert not ReauthenticationSession.objects.filter(user=ctx.worker, auth_time__isnull=False).exists()
    assert not StationOperatorLease.objects.filter(actor=ctx.worker, revoked_at__isnull=True).exists()
    lifecycle.enable_account(ctx.root, ctx.worker.pk)
    ctx.worker.refresh_from_db(); ctx.membership.refresh_from_db()
    # The person signs in again with their own credentials; staff rows are restored per space.
    assert ctx.worker.is_active and ctx.worker.check_password(PASSWORD)
    assert ctx.membership.status == "revoked"


def test_revocation_audits_and_never_touches_credentials(ctx):
    before = (ctx.worker.password, ctx.worker.credential_generation)
    lifecycle.revoke(ctx.manager, ctx.space.pk, ctx.membership.pk, reason="Rota ended")
    ctx.worker.refresh_from_db()
    assert (ctx.worker.password, ctx.worker.credential_generation) == before and ctx.worker.is_active
    event = AuditLog.objects.get(action="staff_role.revoked")
    assert event.meta["membership_id"] == ctx.membership.pk and event.meta["reason"] == "Rota ended"
    assert PASSWORD not in str(event.meta)


@pytest.mark.parametrize("reason", ["x" * 201, 5, ["list"]])
def test_reason_validation_is_atomic(ctx, reason):
    with pytest.raises(ValidationError):
        lifecycle.revoke(ctx.manager, ctx.space.pk, ctx.membership.pk, reason=reason)
    ctx.membership.refresh_from_db()
    assert ctx.membership.status == "active" and not AuditLog.objects.filter(action="staff_role.revoked").exists()


@pytest.mark.parametrize("module", ["email", "staff.invitations"])
def test_granting_without_email_or_invitation_modules(ctx, module):
    ctx.space.enabled_modules = [key for key in ctx.space.enabled_modules if key != module]
    if module == "staff.invitations":
        ctx.space.enabled_features = [key for key in ctx.space.enabled_features if key != module]
    ctx.space.save(update_fields=["enabled_modules", "enabled_features"])
    row = service.grant(ctx.manager, ctx.space.pk, user_id=ctx.joiner.pk, roles=["handover"])
    assert row.status == "active" and row.assigned_role.slug == "handover"
    ctx.joiner.refresh_from_db()
    assert ctx.joiner.check_password(PASSWORD)


def test_member_can_never_acquire_staff_role(ctx):
    membership = MakerspaceMembership.objects.create(user=ctx.member, makerspace=ctx.space,
        assigned_role=ctx.space.roles.get(slug="member"), role="member")
    with pytest.raises(APIException):
        set_membership_roles(makerspace=ctx.space, actor=ctx.root, membership=membership,
                             roles=[ctx.space.roles.get(slug="handover")])


@pytest.mark.parametrize("operation", ["revoke", "disable"])
def test_lifecycle_audit_failure_rolls_back_credentials_and_membership(ctx, monkeypatch, operation):
    before = (ctx.worker.password, ctx.worker.credential_generation)

    def unavailable(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr(lifecycle, "record", unavailable)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        if operation == "disable":
            lifecycle.disable_account(ctx.root, ctx.worker.pk, reason="Audit down")
        else:
            lifecycle.revoke(ctx.manager, ctx.space.pk, ctx.membership.pk)
    ctx.worker.refresh_from_db(); ctx.membership.refresh_from_db()
    assert ctx.worker.is_active and (ctx.worker.password, ctx.worker.credential_generation) == before
    assert ctx.membership.status == "active"


def test_mfa_reset_leaves_no_pending_challenges(ctx):
    from uuid import uuid4
    from datetime import timedelta
    from apps.accounts import mfa_reset
    from apps.accounts.models_mfa import UserMFA, MFAChallenge
    UserMFA.objects.create(user=ctx.worker, secret="encrypted", enabled_at=timezone.now())
    row = MFAChallenge.objects.create(user=ctx.worker, token_digest="m" * 64,
        credential_fingerprint="f" * 64, auth_generation="g" * 64, mfa_version=uuid4(),
        expires_at=timezone.now() + timedelta(minutes=5))
    assert mfa_reset.reset(ctx.root, ctx.worker, "Lost phone") == mfa_reset.RULE_SUPERADMIN
    row.refresh_from_db()
    mfa = UserMFA.objects.get(user=ctx.worker)
    assert row.consumed_at is not None and mfa.enabled_at is None and mfa.secret == ""
