"""Invitations set up only their bound account, with live authority and snapshots."""
import pytest as _pytest_stale

# STALE (R3 test phase): owner decision #63 (unified accounts) retired the separate staff
# account; d55545d7 removed apps.accounts.staff_accounts / the staff-account invitation
# mutate path. Replacement coverage: tests/admin_api/test_staff_roles_api.py.
_pytest_stale.skip("staff accounts retired by #63 (d55545d7)", allow_module_level=True)

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle, staff_account_services as service
from apps.accounts.models import StaffInvitation, User
from apps.accounts.services_staff_invitations import mutate, resend_account
from apps.accounts.staff_invitation_acceptance import accept, GENERIC_ERROR
from apps.makerspaces.role_assignments import set_membership_roles
from .p3_helpers import PASSWORD, context

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def ctx(settings):
    return context(settings)


def invited(ctx, roles=None, machine_type_ids=()):
    user, invitation = service.create(ctx.manager, ctx.space.pk, display_name="Invited",
        email="same@example.test", roles=roles or ["event_manager", "booking_manager"],
        machine_type_ids=machine_type_ids)
    return user, *invitation


def redeem(ctx, token):
    return accept(None, token=token, makerspace_slug=ctx.space.slug, password=PASSWORD)


def test_accept_sets_only_bound_account_password_and_keeps_complete_roles(ctx):
    member = User.objects.create_user("same-address-member", email="same@example.test", password=PASSWORD)
    original = member.password
    user, row, raw = invited(ctx)
    before = user.makerspace_memberships.get().pk
    assert row.account_id == user.pk and row.credential_generation == 0
    assert row.role_snapshot == ["booking_manager", "event_manager"]
    assert row.token_digest != raw
    assert "access" not in redeem(ctx, raw)
    user.refresh_from_db(); member.refresh_from_db(); row.refresh_from_db()
    assert user.check_password(PASSWORD) and user.email_verified_at and not user.must_change_password
    assert member.password == original and not member.makerspace_memberships.exists()
    assert row.accepted_by_id == user.pk and user.makerspace_memberships.get().pk == before
    assert user.makerspace_memberships.get().additional_roles.get().role.slug == "booking_manager"
    with pytest.raises(APIException, match=GENERIC_ERROR):
        redeem(ctx, raw)


@pytest.mark.parametrize("change", ["inviter_demoted", "inviter_inactive", "roles", "scopes", "generation",
                                     "usable_password", "deactivated", "expired", "revoked", "archived"])
def test_redemption_rechecks_every_fence(ctx, change):
    from apps.machines.models import MachineType
    from apps.machines.models_membership_scope import MembershipMachineTypeScope
    kind = MachineType.objects.create(makerspace=ctx.space, slug="invite-laser", name="Laser")
    user, row, raw = invited(ctx, ["machine_manager", "event_manager"], [kind.pk])
    membership = user.makerspace_memberships.get()
    if change == "inviter_demoted":
        service.change(ctx.root, ctx.space.pk, ctx.manager.pk, roles=["event_manager"])
    elif change == "inviter_inactive":
        lifecycle.deactivate(ctx.root, ctx.space.pk, ctx.manager.pk)
    elif change == "roles":
        service.change(ctx.peer, ctx.space.pk, user.pk, roles=["handover"])
    elif change == "scopes":
        MembershipMachineTypeScope.objects.filter(membership=membership).delete()
    elif change == "generation":
        User.objects.filter(pk=user.pk).update(credential_generation=1)
    elif change == "usable_password":
        user.set_password(PASSWORD); user.save(update_fields=["password"])
    elif change == "deactivated":
        lifecycle.deactivate(ctx.manager, ctx.space.pk, user.pk)
    elif change == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1); row.save()
    elif change == "revoked":
        mutate(ctx.manager, row)
    else:
        ctx.space.archived_at = timezone.now(); ctx.space.save(update_fields=["archived_at"])
    with pytest.raises(APIException, match=GENERIC_ERROR):
        redeem(ctx, raw)
    row.refresh_from_db()
    assert row.accepted_at is None


def test_resend_revokes_old_bearer_and_revoke_is_final(ctx):
    user, old, raw = invited(ctx)
    current, new_raw = resend_account(ctx.peer, ctx.space.pk, user.pk)
    old.refresh_from_db()
    assert old.revoked_at and current.created_by_id == ctx.peer.pk and new_raw != raw
    with pytest.raises(APIException):
        redeem(ctx, raw)
    mutate(ctx.peer, current)
    with pytest.raises(APIException):
        redeem(ctx, new_raw)


@pytest.mark.parametrize("reset_first", [True, False])
def test_reset_and_redemption_both_orders(ctx, reset_first):
    user, row, raw = invited(ctx)
    if not reset_first:
        redeem(ctx, raw)
    result = lifecycle.set_password(ctx.manager, ctx.space.pk, user.pk, generate=True)
    with pytest.raises(APIException):
        redeem(ctx, raw)
    user.refresh_from_db(); row.refresh_from_db()
    assert user.check_password(result["generated_password"]) and user.must_change_password
    assert user.credential_generation == 1
    assert (row.revoked_at is not None) == reset_first


def test_legacy_unbound_invitation_cannot_create_an_account(ctx):
    from apps.accounts.mfa_challenges import digest
    from apps.makerspaces.secrets import encrypt_value
    token = "x" * 40
    row = StaffInvitation.objects.create(makerspace=ctx.space, role=ctx.space.roles.get(slug="handover"),
        email_ciphertext=encrypt_value("legacy@example.test"), created_by=ctx.manager,
        token_digest=digest(token), expires_at=timezone.now() + timedelta(days=1))
    with pytest.raises(APIException):
        redeem(ctx, token)
    row.refresh_from_db()
    assert row.failed_attempts == 1
    assert not User.objects.filter(email="legacy@example.test").exists()


def test_invitation_is_not_redeemable_in_another_tenant(ctx):
    user, row, raw = invited(ctx)
    with pytest.raises(APIException, match=GENERIC_ERROR):
        accept(None, token=raw, makerspace_slug=ctx.other.slug, password=PASSWORD)
    user.refresh_from_db(); row.refresh_from_db()
    assert not user.has_usable_password() and row.accepted_at is None


def test_delivery_failure_keeps_account_and_no_provider_secrets(ctx, monkeypatch, caplog):
    from apps.accounts.staff_invitation_delivery import deliver
    user, row, raw = invited(ctx)
    def unavailable(**kwargs):
        assert not kwargs["persist_body"]
        assert "new staff account" in kwargs["text_body"]
        raise RuntimeError("smtp-secret")
    monkeypatch.setattr("apps.accounts.staff_invitation_delivery.dispatch_email", unavailable)
    assert deliver(row, raw)["delivery_status"] == "unavailable"
    assert "smtp-secret" not in caplog.text and raw not in caplog.text
    assert User.objects.filter(pk=user.pk).exists()
