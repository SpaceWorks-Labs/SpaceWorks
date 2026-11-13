from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.bookings import services_staff_grants as services
from apps.bookings.models import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite
from apps.makerspaces.models import MakerspaceMembership
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

pytestmark = pytest.mark.django_db


def invite_fixture(**options):
    tenant, manager, user, resource, grant, member = grant_fixture()
    grant.delete()
    row, token = services.create_invite(resource, actor=manager, permissions=["check_in"], **options)
    return tenant, manager, user, resource, row, token


def test_seven_day_hmac_single_use_verified_email_and_audit():
    tenant, _, user, resource, row, token = invite_fixture(email="BOOKING-GRANTS@example.test")
    assert timedelta(days=7)-timedelta(seconds=3) <= row.expires_at-row.created_at <= timedelta(days=7)
    assert token not in row.token_digest and len(row.token_digest) == 64
    grant = services.redeem_invite(token, actor=user)
    assert grant.space == resource and grant.user == user and grant.permissions == ["check_in"]
    with pytest.raises(NotFound):
        services.redeem_invite(token, actor=user)
    assert set(AuditLog.objects.filter(makerspace=tenant).values_list("action", flat=True)) >= {
        "booking.staff_grant_invited", "booking.staff_grant_created", "booking.staff_grant_invite_redeemed"}
    assert token not in str(list(AuditLog.objects.values("meta")))
    listed = client_for(row.created_by).get(reverse("admin-booking-staff-invites", args=[resource.pk]))
    assert token not in str(listed.data) and "token_digest" not in str(listed.data)


@pytest.mark.parametrize("state", ["expired", "revoked", "used", "creator_revoked", "creator_suspended", "creator_missing", "feature_off"])
def test_redemption_revalidates_locked_invite_creator_and_feature(state):
    tenant, manager, user, _, row, token = invite_fixture()
    if state == "expired":
        row.expires_at = timezone.now()-timedelta(seconds=1)
        row.save(update_fields=["expires_at"])
    elif state == "revoked":
        services.revoke_invite(row, actor=manager)
    elif state == "used":
        row.redeemed_at = timezone.now()
        row.save(update_fields=["redeemed_at"])
    elif state == "creator_revoked":
        MakerspaceMembership.all_tracks.filter(user=manager, makerspace=tenant).update(status="revoked")
    elif state == "creator_suspended":
        type(manager).objects.filter(pk=manager.pk).update(access_status="suspended")
    elif state == "creator_missing":
        BookingSpaceStaffGrantInvite.objects.filter(pk=row.pk).update(created_by=None)
    else:
        tenant.enabled_features.remove("bookings.staff_grants")
        tenant.save(update_fields=["enabled_features"])
    with pytest.raises((NotFound, PermissionDenied, ValidationError)):
        services.redeem_invite(token, actor=user)
    assert not BookingSpaceStaffGrant.objects.exists()


@pytest.mark.parametrize("state", ["unverified", "mismatch", "wrong_tenant"])
def test_bound_invite_never_widens_identity_or_tenant(state):
    tenant, _, user, _, row, token = invite_fixture(email="booking-grants@example.test")
    if state == "unverified":
        user.email_verified_at = None
        user.save(update_fields=["email_verified_at"])
    elif state == "mismatch":
        user.email = "other@example.test"
        user.save(update_fields=["email"])
    with pytest.raises((PermissionDenied, NotFound)):
        services.redeem_invite(token, actor=user, makerspace_id=tenant.pk+1 if state == "wrong_tenant" else tenant.pk)
    row.refresh_from_db()
    assert row.redeemed_at is None and not BookingSpaceStaffGrant.objects.exists()


def test_non_escalation_and_grantees_cannot_delegate(monkeypatch):
    _, manager, user, resource, grant, _ = grant_fixture()
    with pytest.raises(PermissionDenied):
        services.create_invite(resource, actor=user, permissions=["edit_details"])
    row, token = services.create_invite(resource, actor=manager, permissions=["check_in"])
    grant.delete()
    monkeypatch.setattr(services, "ADAPTER", replace(services.ADAPTER, can=lambda *args: False))
    with pytest.raises(PermissionDenied):
        services.redeem_invite(token, actor=user)
    row.refresh_from_db()
    assert row.redeemed_at is None


@pytest.mark.parametrize("permissions", [[], ["edit_details", "edit_details"], ["manage_bookings"], ["manage_payments"]])
def test_invalid_permission_sets_are_refused(permissions):
    _, manager, _, resource, _, _ = grant_fixture()
    with pytest.raises(ValidationError):
        services.create_invite(resource, actor=manager, permissions=permissions)


def test_live_update_revocation_and_no_credential_delivery_persistence(monkeypatch, django_capture_on_commit_callbacks):
    _, manager, user, resource, grant, _ = grant_fixture()
    calls = []
    monkeypatch.setattr("apps.integrations.dispatch_outbox.dispatch_email", lambda **kwargs: calls.append(kwargs))
    with django_capture_on_commit_callbacks(execute=True):
        _, token = services.create_invite(resource, actor=manager, permissions=["check_in"], email=user.email, send_email=True)
    assert calls[0]["persist_body"] is False and calls[0]["sync"] is True
    assert f"/staff/booking-invite#token={token}" in calls[0]["text_body"]
    services.update_permissions(grant, actor=manager, permissions=["manage_reservations"])
    assert grant.permissions == ["edit_details"]  # service returns a freshly locked row
    grant.refresh_from_db()
    assert grant.permissions == ["manage_reservations"]
    services.revoke_grant(grant, actor=manager)
    with pytest.raises(ValidationError):
        services.update_permissions(grant, actor=manager, permissions=["edit_details"])


@pytest.mark.django_db(transaction=True)
def test_two_redemptions_have_one_transactional_winner():
    _, _, user, _, row, token = invite_fixture()
    barrier = Barrier(2)

    def redeem():
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            try:
                return services.redeem_invite(token, actor=user).pk
            except NotFound:
                return None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: redeem(), range(2)))
    assert sum(value is not None for value in results) == 1
    assert BookingSpaceStaffGrant.objects.count() == 1


def test_local_manager_can_revoke_grants_and_invites():
    _, manager, _, resource, grant, _ = grant_fixture()
    row, _ = services.create_invite(resource, actor=manager, permissions=["check_in"])
    assert services.revoke_grant(grant, actor=manager).revoked_at is not None
    assert services.revoke_invite(row, actor=manager).revoked_at is not None


@pytest.mark.django_db(transaction=True)
def test_grantee_mutation_and_revocation_serialize_on_the_resource():
    from apps.bookings import services as bookings
    from apps.bookings.models import BookableSpace
    tenant, manager, user, resource, grant, _ = grant_fixture()
    barrier = Barrier(2)

    def perform(kind):
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            if kind == "revoke":
                services.revoke_grant(grant, actor=manager)
                return "revoked"
            try:
                bookings.update_space(resource, actor=user, description="Authorized before revocation")
                return "edited"
            except PermissionDenied:
                return "refused"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(perform, ["revoke", "edit"]))
    assert results[0] == "revoked" and results[1] in {"edited", "refused"}
    with pytest.raises(PermissionDenied):
        bookings.update_space(resource, actor=user, description="Never authorized after revocation")
    assert BookableSpace.objects.get(pk=resource.pk).description != "Never authorized after revocation"
