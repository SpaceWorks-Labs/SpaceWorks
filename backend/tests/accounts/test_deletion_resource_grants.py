"""Account departure permanently revokes resource-only authority."""

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts import account_deletion
from apps.accounts.account_deletion_discovery import tenant_ids
from apps.accounts.account_restore import identifier_fingerprint, restore_locked
from apps.audit.models import AuditLog
from apps.bookings import booking_authority
from apps.bookings.models import BookableSpace, BookingSpaceStaffGrant
from apps.events import event_authority
from apps.events.models import Event, EventStaffGrant
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts import deletion_factories as f
from tests.accounts.test_support_m1d import account, m1d_config, proven

pytestmark = pytest.mark.django_db


def resources(user):
    result = []
    for kind in ("event", "booking"):
        tenant = f.space()
        tenant.enabled_modules = sorted(set(tenant.enabled_modules) | {"events", "bookings"})
        tenant.enabled_features = sorted(set(tenant.enabled_features) | {"bookings.staff_grants"})
        tenant.save(update_fields=["enabled_modules", "enabled_features"])
        if kind == "event":
            target = Event.objects.create(makerspace=tenant, title="Delegated workshop",
                starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1))
            grant = EventStaffGrant.objects.create(makerspace=tenant, event=target, user=user,
                                                   permissions=["edit_details"])
            policy = event_authority
        else:
            target = BookableSpace.objects.create(makerspace=tenant, name="Delegated room")
            grant = BookingSpaceStaffGrant.objects.create(makerspace=tenant, space=target, user=user,
                                                          permissions=["edit_details"])
            policy = booking_authority
        result.append((tenant, target, grant, policy))
    return result


def test_grant_only_tenants_are_discovered_and_restore_does_not_revive_authority():
    user, other = account(), account()
    grants, foreign = resources(user), resources(other)
    assert not MakerspaceMembership.objects.filter(user=user).exists()
    assert tenant_ids(user) == {row[0].pk for row in grants}
    assert [policy.can(user, target, "edit_details") for _, target, _, policy in grants] == [True, True], [g.__class__.__name__ for _, _, g, _ in grants]

    account_deletion.request_deletion(proven(user))
    user.refresh_from_db()
    for tenant, _, grant, _ in grants:
        grant.refresh_from_db()
        assert grant.revoked_at == user.deletion_requested_at and grant.revoked_by_id == user.pk
        assert AuditLog.objects.filter(makerspace=tenant, target_id=str(grant.pk),
            action__in=["event.staff_grant_revoked", "booking.staff_grant_revoked"],
            meta__reason="account_deletion").count() == 1
    with transaction.atomic():
        restore_locked(user, fingerprint=identifier_fingerprint(user),
                       new_password="Fresh recovery password 789!")
    assert all(not policy.can(user, target, "edit_details") for _, target, _, policy in grants)
    for _, _, grant, _ in foreign:
        grant.refresh_from_db()
        assert grant.revoked_at is None


def test_resource_revocation_and_audits_roll_back_with_failed_departure(monkeypatch):
    user = account()
    grants = resources(user)
    req = proven(user)
    original = account_deletion.audit.record

    def fail(actor, action, **kwargs):
        if action == "account.deletion_requested":
            raise RuntimeError("departure did not commit")
        return original(actor, action, **kwargs)

    monkeypatch.setattr(account_deletion.audit, "record", fail)
    with pytest.raises(RuntimeError):
        account_deletion.request_deletion(req)
    for _, _, grant, _ in grants:
        grant.refresh_from_db()
        assert grant.revoked_at is None and grant.revoked_by_id is None
    assert not AuditLog.objects.filter(actor=user, meta__reason="account_deletion").exists()
