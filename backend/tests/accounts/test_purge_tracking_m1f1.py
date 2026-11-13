"""Phase 1f-1 tracking follows the resumable phase 1d deletion contract."""

from contextlib import nullcontext
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.accounts.account_deletion import request_deletion
from apps.accounts.account_deletion_discovery import tenant_ids
from apps.accounts.models_activity import AttestationVerificationLog, DeviceActivityDay
from apps.accounts.models_devices import NativeAppRegistration
from apps.integrations.models import EmailLog, NotificationDeliveryLog, PushDevice
from apps.integrations.models_tracking import PushDeliveryAttempt, SmsSendLog
from apps.inventory.models import InventoryProduct
from apps.inventory.models_tracking import InventoryStockSnapshot
from apps.machines.models import MachineUsageEntry
from apps.machines.models_tracking import ConsumableCostRecord, MachineStatusEvent
from apps.notifications.models import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from tests.accounts import deletion_factories as f
from tests.accounts.account_factories import device_grant
from tests.accounts.push_factories import member_push
from tests.accounts.test_purge_resume_m1d import close_gate, set_gate
from tests.accounts.test_support_m1d import account, due, m1d_config, proven, purge
from tests.encryption.conftest import enabled_encryption
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


def grant(user):
    """An archived (Stage A) account can only hold revoked grants: the device
    context guard refuses live authority once deletion is requested."""
    registration, _ = NativeAppRegistration.objects.get_or_create(
        makerspace=None, app_id="test.purge-tracking", platform="apple", environment="production",
        defaults={"verifier_config_key": "test", "status": "approved"},
    )
    revoked = {"status": "revoked", "revoked_at": timezone.now()} if user.deletion_requested_at else {}
    return device_grant(user, registration, **revoked)


def device(user, tenant, *, device_grant=None):
    return PushDevice.objects.create(
        user=user, makerspace=tenant, device_grant=device_grant or grant(user),
        provider="apns", environment="production", token_ciphertext="private-token",
        token_fingerprint=uuid4().hex * 2,
    )


def inbox(user, tenant):
    return NotificationInboxRow.objects.create(
        user=user, makerspace=tenant, event_key=uuid4(), audience="member",
        feature="events", event="registered", title="Private member notification",
    )


def staff_attempt(recipient, push):
    log = NotificationDeliveryLog.objects.create(
        makerspace=push.makerspace, channel="native_push", feature="events",
        event="registered", text_body="Retained operational history", status="sent",
    )
    return PushDeliveryAttempt.objects.create(recipient=recipient, push_device=push, delivery_log=log)


def snapshot(row):
    return type(row).objects.filter(pk=row.pk).values().get()


def test_activity_only_participation_deletes_selected_and_null_activity_but_keeps_grants():
    user, other, tenant = due(account()), account(), f.space()
    own_grant, other_grant = grant(user), grant(other)
    assert own_grant.status == "revoked" and own_grant.revoked_at
    before = snapshot(own_grant)
    owned, unrelated = [], []
    for space in (tenant, None):
        for target, rows in ((own_grant, owned), (other_grant, unrelated)):
            rows.append(DeviceActivityDay.objects.create(
                grant=target, makerspace=space, platform="apple", local_day=timezone.localdate(),
            ))
    assert tenant_ids(user) == {tenant.pk}
    assert purge(user) == {"purged": 1, "skipped": 0, "failed": 0}
    assert not DeviceActivityDay.objects.filter(pk__in=[row.pk for row in owned]).exists()
    assert DeviceActivityDay.objects.filter(pk__in=[row.pk for row in unrelated]).count() == 2
    assert snapshot(own_grant) == before
    assert purge(user)["purged"] == 0


def test_null_activity_without_any_tenant_is_deleted_globally():
    user = due(account())
    row = DeviceActivityDay.objects.create(
        grant=grant(user), platform="apple", local_day=timezone.localdate(),
    )
    assert tenant_ids(user) == set()
    assert purge(user)["purged"] == 1
    assert not DeviceActivityDay.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize("ownership", ["member_inbox", "member_device", "staff_recipient",
                                     "staff_device", "staff_legacy_device"])
def test_push_history_is_removed_through_each_ownership_path_without_erasing_other_users(ownership):
    user, other, tenant = due(account()), account(), f.space()
    other_push, other_inbox = device(other, tenant), inbox(other, tenant)
    kept_member = member_push(tenant, other, other_push, inbox_row=other_inbox)
    kept_staff = staff_attempt(other, other_push)
    retained = [(row, snapshot(row)) for row in (other_push, other_inbox, kept_member, kept_staff)]
    if ownership == "member_inbox":
        # The device has moved to another account; the original inbox still owns delivery history.
        removed = member_push(tenant, user, other_push, inbox_row=inbox(user, tenant))
    elif ownership == "member_device":
        # Addressed to the other account but sent to a device this user still owns.
        removed = member_push(tenant, other, device(user, tenant), inbox_row=other_inbox)
    elif ownership == "staff_recipient":
        # No remaining device/inbox belongs to user: discover and erase by the recipient snapshot.
        removed = staff_attempt(user, other_push)
    else:
        removed = staff_attempt(None if ownership == "staff_legacy_device" else other, device(user, tenant))
    if isinstance(removed, PushDeliveryAttempt):
        retained.append((removed.delivery_log, snapshot(removed.delivery_log)))
    assert tenant_ids(user) == {tenant.pk}
    assert purge(user) == {"purged": 1, "skipped": 0, "failed": 0}
    assert not type(removed).objects.filter(pk=removed.pk).exists()
    for row, before in retained:
        assert snapshot(row) == before
    assert purge(user)["purged"] == 0


def test_stage_a_only_deactivates_push_and_preserves_tracking_until_stage_b():
    user, tenant = account(), f.space()
    push = device(user, tenant)
    # Stage A cancels only in-flight children; terminal telemetry waits for Stage B.
    member = member_push(tenant, user, push, inbox_row=inbox(user, tenant), status="sent", attempts=1)
    staff = staff_attempt(user, push)
    activity = DeviceActivityDay.objects.create(
        grant=push.device_grant, makerspace=tenant, platform="apple", local_day=timezone.localdate(),
    )
    before = [(row, snapshot(row)) for row in (member, staff, activity)]
    request_deletion(proven(user))
    push.refresh_from_db()
    assert not push.active and push.invalidated_at
    for row, values in before:
        assert snapshot(row) == values


def test_immutable_usage_attribution_and_anonymous_tracking_survive_purge_unchanged():
    user, tenant, started = due(account()), f.space(), timezone.now() - timedelta(hours=2)
    target = machine(tenant)
    usage = MachineUsageEntry.objects.create(machine=target, member=user, started_at=started, hours="1.50")
    product = InventoryProduct.objects.create(
        makerspace=tenant, name="Filament", total_quantity=10, available_quantity=10,
    )
    rows = [usage,
        ConsumableCostRecord.objects.create(makerspace=tenant, source_kind="manual_adjustment", source_id=1,
            quantity="2.00", measurement_unit="grams", unit_price_minor_per_measurement_unit="3.00",
            cost_total_minor=6, currency="USD"),
        InventoryStockSnapshot.objects.create(makerspace=tenant, product=product, local_day=timezone.localdate(),
            available=10, issued=0, total=10, out_of_stock=False, below_reorder=False),
        MachineStatusEvent.objects.create(makerspace=tenant, machine=target,
            from_status="available", to_status="maintenance", source="manual"),
        SmsSendLog.objects.create(makerspace=tenant, status="sent"),
        SmsSendLog.objects.create(status="failed"),
        AttestationVerificationLog.objects.create(platform="apple", mode="strict", outcome="sent"),
    ]
    before = [(row, snapshot(row)) for row in rows]
    assert tenant_ids(user) == {tenant.pk}
    assert purge(user)["purged"] == 1
    assert user.account_purged_at and user.display_name == "Deleted member" and not user.email
    for row, values in before:
        assert snapshot(row) == values
    usage.refresh_from_db()
    assert usage.member_id == user.pk and usage.started_at == started
    assert purge(user)["purged"] == 0


@pytest.mark.parametrize("encrypted", [False, True], ids=["plaintext", "scoped-pii"])
def test_email_scrub_clears_provider_correlation_but_retains_anonymous_outcomes(encrypted):
    with enabled_encryption(dual_read=False) if encrypted else nullcontext():
        user, other, tenant, now = due(account()), account(), f.space(), timezone.now()
        owned = []
        for space in (tenant, None):
            for recipient in (user, None):
                owned.append(EmailLog.objects.create(
                    makerspace=space, recipient=recipient,
                    to_email=user.email.upper() if recipient is None else "previous@example.test",
                    subject="Private", text_body="Private", html_body="Private",
                    provider_message_id=uuid4().hex, provider_source="own", status="sent",
                    bounced_at=now, complained_at=now,
                ))
        unrelated = [EmailLog.objects.create(makerspace=space, recipient=other, to_email=other.email,
            subject="Retained", provider_message_id="other-provider-id", bounced_at=now)
            for space in (tenant, None)]
        before = [snapshot(row) for row in unrelated]
        assert purge(user)["purged"] == 1
        for row in owned:
            row.refresh_from_db()
            assert row.to_email == row.subject == row.text_body == row.html_body == row.provider_message_id == ""
            assert row.bounced_at == row.complained_at == now
            assert row.provider_source == "own" and row.status == "sent"
        assert [snapshot(row) for row in unrelated] == before


@pytest.mark.django_db(transaction=True)
def test_gated_tenant_preserves_its_push_and_email_history_and_defers_global_activity_cleanup():
    user, other, one, two = due(account()), account(), f.space(), f.space()
    own_grant, other_grant = grant(user), grant(other)
    per_tenant = {}
    activity = [DeviceActivityDay.objects.create(
        grant=own_grant, platform="apple", local_day=timezone.localdate(),
    )]
    for tenant in (one, two):
        push = device(user, tenant, device_grant=own_grant)
        member = member_push(tenant, user, push, inbox_row=inbox(user, tenant))
        staff = staff_attempt(user, device(other, tenant, device_grant=other_grant))
        email = EmailLog.objects.create(makerspace=tenant, recipient=user, to_email=user.email,
            subject="Private", provider_message_id="private-provider-id")
        activity.append(DeviceActivityDay.objects.create(
            grant=own_grant, makerspace=tenant, platform="apple", local_day=timezone.localdate(),
        ))
        per_tenant[tenant.pk] = (member, staff, email)
    gate = close_gate(two)
    frozen = [(row, snapshot(row)) for row in per_tenant[two.pk]]
    assert purge(user) == {"purged": 0, "failed": 0, "skipped": 1}
    member, staff, email = per_tenant[one.pk]
    assert not MemberPushDelivery.objects.filter(pk=member.pk).exists()
    assert not PushDeliveryAttempt.objects.filter(pk=staff.pk).exists()
    email.refresh_from_db()
    assert email.provider_message_id == email.to_email == ""
    assert DeviceActivityDay.objects.filter(pk__in=[row.pk for row in activity]).count() == 3
    for row, before in frozen:
        assert snapshot(row) == before
    assert not user.account_purged_at and user.email
    set_gate(gate, closed=False)
    assert purge(user) == {"purged": 1, "failed": 0, "skipped": 0}
    member, staff, email = per_tenant[two.pk]
    assert not MemberPushDelivery.objects.filter(pk=member.pk).exists()
    assert not PushDeliveryAttempt.objects.filter(pk=staff.pk).exists()
    email.refresh_from_db()
    assert email.provider_message_id == email.to_email == ""
    assert not DeviceActivityDay.objects.filter(grant__user=user).exists()
