"""Invitation regressions adapted to account-bound initial password setup."""
import pytest as _pytest_stale

# STALE (R3 test phase): owner decisions #63/#66 retired the separate staff account and the
# Space Manager's create/set-password/deactivate/resend-account paths (d55545d7, d7f674a7).
# Replacement coverage: tests/admin_api/test_staff_roles_api.py and the /control/ disable tests.
_pytest_stale.skip("staff accounts retired by #63/#66 (d55545d7)", allow_module_level=True)

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from rest_framework.test import APIClient
from rest_framework.exceptions import APIException
from django.utils import timezone

from apps.accounts import staff_account_services as service
from apps.accounts.services_staff_invitations import issue, resend_account, mutate
from apps.accounts.models import StaffInvitation, User
from apps.accounts.staff_invitation_acceptance import GENERIC_ERROR
from apps.accounts.staff_invitation_delivery import deliver
from apps.tenant_migration.gate_runtime import tenant_write
from tests.account_split.p3_helpers import context, client, PASSWORD

pytestmark = pytest.mark.django_db
ACCEPT = "/api/v1/auth/staff-invitations/accept"


@pytest.fixture
def invitations(settings):
    return context(settings)


def invite(ctx, roles=None):
    user, invitation = service.create(ctx.manager, ctx.space.pk, display_name="Invited",
        email="invited@example.test", roles=roles or ["inventory_manager"])
    return user, *invitation


def accept(ctx, raw, password=PASSWORD):
    return APIClient().post(ACCEPT, {"token": raw, "makerspace_slug": ctx.space.slug,
                                    "password": password}, format="json")


def test_email_off_uses_admin_set_password_instead_of_bearer_onboarding(invitations):
    ctx = invitations
    ctx.space.enabled_modules = [key for key in ctx.space.enabled_modules if key != "email"]
    ctx.space.save(update_fields=["enabled_modules"])
    user, invitation = service.create(ctx.manager, ctx.space.pk, display_name="No mail",
        email="invited@example.test", roles=["handover"])
    assert invitation is None and not StaffInvitation.objects.filter(account=user).exists()
    from apps.accounts.staff_account_lifecycle import set_password
    set_password(ctx.manager, ctx.space.pk, user.pk, password=PASSWORD)
    user.refresh_from_db()
    assert user.check_password(PASSWORD) and user.must_change_password


def test_existing_usable_account_is_never_linked_or_reset(invitations):
    ctx = invitations
    user, _, raw = invite(ctx)
    assert accept(ctx, raw).status_code == 200
    before = user.password
    user.refresh_from_db(); before = user.password
    with pytest.raises(APIException):
        resend_account(ctx.manager, ctx.space.pk, user.pk)
    assert accept(ctx, raw).status_code == 400
    user.refresh_from_db()
    assert user.password == before and User.objects.filter(email=user.email).count() == 1


def test_delivery_failure_keeps_invitation_and_link_without_logging_provider_secrets(invitations, monkeypatch, caplog):
    ctx = invitations
    def fail(**kwargs):
        assert kwargs["persist_body"] is False and kwargs["sync"] is True
        raise RuntimeError("smtp-credential-secret")
    monkeypatch.setattr("apps.accounts.staff_invitation_delivery.dispatch_email", fail)
    user, row, raw = invite(ctx)
    response = deliver(row, raw)
    assert response["delivery_status"] == "unavailable"
    assert parse_qs(urlsplit(response["accept_url"]).fragment)["token"] == [raw]
    assert "smtp-credential-secret" not in caplog.text
    assert accept(ctx, raw).status_code == 200


@pytest.mark.parametrize("state", ["expired", "revoked", "used", "unknown"])
def test_unavailable_invitation_has_one_generic_response(invitations, state):
    ctx = invitations
    user, row, raw = invite(ctx)
    if state == "expired":
        row.expires_at = timezone.now() - timedelta(seconds=1)
    elif state == "revoked":
        row.revoked_at = timezone.now()
    elif state == "used":
        row.accepted_at = timezone.now()
    else:
        raw = "x" * 43
    row.save()
    response = accept(ctx, raw)
    assert response.status_code == 400 and response.json() == {"detail": GENERIC_ERROR}
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_resend_rotates_bearer_and_revoke_prevents_acceptance(invitations):
    ctx = invitations
    user, row, raw = invite(ctx)
    resent, new_raw = resend_account(ctx.manager, ctx.space.pk, user.pk)
    assert new_raw != raw
    row.refresh_from_db()
    assert row.revoked_at and accept(ctx, raw).status_code == 400
    mutate(ctx.manager, resent)
    assert accept(ctx, new_raw).status_code == 400


def test_old_creation_and_cross_tenant_mutations_are_refused(invitations):
    ctx = invitations
    user, row, raw = invite(ctx)
    api = client(ctx.manager)
    base = f"/api/v1/admin/makerspaces/{ctx.space.pk}/staff-invitations"
    response = api.post(base, {"email": "old@example.test",
        "role_id": ctx.space.roles.get(slug="inventory_manager").pk}, format="json")
    assert response.status_code == 400
    assert client(ctx.foreign).post(f"{base}/{row.pk}/revoke", {}, format="json").status_code == 403
    assert accept(ctx, raw).status_code == 200


def test_feature_off_refuses_email_but_admin_set_path_stays_available(invitations):
    ctx = invitations
    ctx.space.enabled_features = [key for key in ctx.space.enabled_features if key != "staff.invitations"]
    ctx.space.save(update_fields=["enabled_features"])
    user, invitation = service.create(ctx.manager, ctx.space.pk, display_name="Feature off",
        email="invited@example.test", roles=["handover"])
    assert invitation is None
    with pytest.raises(APIException):
        resend_account(ctx.manager, ctx.space.pk, user.pk)


def test_accept_failure_is_generic_and_commits_bounded_attempts(invitations):
    ctx = invitations
    user, row, raw = invite(ctx)
    for _ in range(6):
        response = accept(ctx, raw, password="weak")
        assert response.status_code == 400 and response.json() == {"detail": GENERIC_ERROR}
    row.refresh_from_db(); user.refresh_from_db()
    assert row.failed_attempts == 5 and row.accepted_at is None
    assert not user.has_usable_password()


def test_frozen_tenant_cannot_accept_or_change_bound_account(invitations):
    from tests.tenant_migration.source_gate_helpers import close_gate
    ctx = invitations
    user, row, raw = invite(ctx)
    close_gate(ctx.space, ctx.root)
    assert accept(ctx, raw).status_code == 423
    user.refresh_from_db()
    assert not user.has_usable_password() and user.must_change_password


def test_member_with_same_email_is_never_adopted_as_staff(invitations):
    ctx = invitations
    member = User.objects.create_user("separate-member", email="invited@example.test", password=PASSWORD)
    original = member.password
    user, row, raw = invite(ctx)
    assert accept(ctx, raw).status_code == 200
    member.refresh_from_db(); user.refresh_from_db()
    assert member.password == original and not member.makerspace_memberships.exists()
    assert user.pk != member.pk and user.check_password(PASSWORD)
