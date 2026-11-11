"""BK-B lifecycle acceptance through real cancellation, undo, outbox and delivery."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from apps.accounts.rbac import Action
from apps.bookings import services
from apps.bookings.models import BookableSpace, Booking, BookingSpaceStaffGrant
from apps.bookings.notifications import BOOKING_NOTIFICATION_EVENTS
from apps.bookings.services_restore import restore_booking
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.email_preferences import address_hash
from apps.integrations.email_templates_fablab import bookings_context
from apps.integrations.email_templates_registry import get_entry
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_tasks import deliver_envelope
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from apps.operations.cancellation_restore import RestoreRefused
from tests.machines.certification_helpers import _manager, _member, _space

pytestmark = pytest.mark.django_db


def cancelled(monkeypatch, status="confirmed"):
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    tenant = _space("restored-notifications", modules=("bookings", "email", "notifications"), certifications=False)
    tenant.enabled_features = sorted(set(tenant.enabled_features) | {"bookings.staff_tools"})
    tenant.booking_requester_notifications_enabled = True
    tenant.save(update_fields=["enabled_features", "booking_requester_notifications_enabled"])
    actor, _ = _manager(tenant, "restore-manager", actions=(Action.MANAGE_BOOKINGS,))
    member, _ = _member(tenant, "restore-requester")
    member.phone = "987654321987"
    member.email_verified_at = timezone.now()
    member.save(update_fields=["phone", "email_verified_at"])
    resource = BookableSpace.objects.create(
        makerspace=tenant, name="Restored workshop", approval_mode=(
            BookableSpace.ApprovalMode.INSTANT if status == "confirmed" else BookableSpace.ApprovalMode.APPROVE
        ), custom_form=[{"id": "private", "label": "Private answer", "type": "short_text", "options": [], "required": False}],
    )
    start = timezone.now() + timedelta(days=1)
    booking = services.create_booking(
        resource, member=member, starts_at=start, ends_at=start + timedelta(hours=1),
        note="PRIVATE-NOTE-SENTINEL", custom_answers={"private": "PRIVATE-ANSWER-SENTINEL"},
    )
    booking = services.cancel_booking(booking, actor=actor)
    # Keep the real outbox boundary; SMTP is the only transport replaced below.
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection",
                        lambda makerspace: (None, "staff@example.test"))
    send = Mock(return_value=1)
    monkeypatch.setattr(EmailMultiAlternatives, "send", send)
    message = Mock(wraps=EmailMultiAlternatives)
    monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives", message)
    return tenant, actor, member, resource, booking, send, message


def restored_envelopes(tenant):
    return NotificationEnvelope.objects.filter(makerspace=tenant, source_kind__in=[
        "bookings.lifecycle", "bookings.grant_alert"], event="restored").order_by("id")


def deliver_restored(tenant, *, audience=None):
    rows = restored_envelopes(tenant)
    if audience:
        rows = rows.filter(audience=audience)
    for pk in rows.values_list("pk", flat=True):
        deliver_envelope(pk)


def restored_logs(tenant):
    return EmailLog.objects.filter(makerspace=tenant, stream="bookings", event="restored").order_by("id")


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_real_cancel_undo_dispatches_registered_private_safe_templates(
    monkeypatch, django_capture_on_commit_callbacks, status,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch, status)
    other = _space("restored-other", certifications=False)
    foreign, _ = _manager(other, "foreign-manager", actions=(Action.MANAGE_BOOKINGS,))
    assert "restored" in BOOKING_NOTIFICATION_EVENTS
    assert "restored" in FEATURE_EVENTS["bookings"]
    for audience in ("requester", "staff"):
        entry = get_entry("bookings", audience, "restored")
        assert entry is not None
        assert entry.sample_context["event_name"] == "restored"
        assert "next_steps" in entry.sample_context

    with django_capture_on_commit_callbacks(execute=True):
        restored = restore_booking(booking, actor=actor)
        assert restored_envelopes(tenant).exists()
        assert not send.called
    assert restored.status == status
    deliver_restored(tenant)
    logs = list(restored_logs(tenant))
    assert {(log.to_email, log.audience) for log in logs} == {
        (member.email, "requester"), (actor.email, "staff"),
    }
    assert all(log.to_email != foreign.email for log in logs)
    when = bookings_context(restored, "restored")["booking"].when
    for log in logs:
        assert log.status == "sent"
        assert f"Status: {status}" in log.text_body
        assert resource.name in log.text_body and when in log.text_body
        assert "cancellation was undone" in log.text_body
        assert "pending means staff still need to approve" in log.text_body
        _deliver(log)
        assert log.status == "sent"
    assert send.call_count == len(logs) == 2
    rendered = " ".join(str(call.kwargs) for call in message.call_args_list)
    for forbidden in ("PRIVATE-NOTE-SENTINEL", "PRIVATE-ANSWER-SENTINEL", str(booking.public_token), member.phone):
        assert forbidden not in rendered


@pytest.mark.parametrize("gate", ["requester_toggle", "resource_toggle", "matrix", "email_module", "suppression", "personal", "staff_opt_out"])
def test_restored_notifications_preserve_dispatch_gates(
    monkeypatch, django_capture_on_commit_callbacks, gate,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    if gate == "requester_toggle":
        tenant.booking_requester_notifications_enabled = False
        tenant.save(update_fields=["booking_requester_notifications_enabled"])
    elif gate == "resource_toggle":
        resource.requester_notifications_enabled = False
        resource.save(update_fields=["requester_notifications_enabled"])
    elif gate == "matrix":
        NotificationPreference.objects.create(makerspace=tenant, feature="bookings", channel="email", enabled=False)
    elif gate == "email_module":
        tenant.enabled_modules = [key for key in tenant.enabled_modules if key != "email"]
        tenant.save(update_fields=["enabled_modules"])
    elif gate == "suppression":
        EmailSuppression.objects.create(makerspace=tenant, address_hash=address_hash(tenant.pk, member.email), reason="bounce")
    elif gate == "personal":
        MemberNotificationPreference.objects.create(makerspace=tenant, user=member, feature="bookings", channel="email", enabled=False)
    else:
        MakerspaceMembership.all_tracks.filter(makerspace=tenant, user=actor).update(receives_notifications=False)
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    deliver_restored(tenant)
    logs = list(restored_logs(tenant))
    for log in logs:
        _deliver(log)
    sent = [log for log in logs if log.status == "sent"]
    assert len(sent) == (0 if gate in {"matrix", "email_module"} else 1)
    assert all(log.audience == ("requester" if gate == "staff_opt_out" else "staff") for log in sent)
    assert send.call_count == len(sent)


@pytest.mark.parametrize("gate", ["email_module", "personal", "suppression"])
def test_queued_restore_email_rechecks_delivery_gates(
    monkeypatch, django_capture_on_commit_callbacks, gate,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    envelope = restored_envelopes(tenant).get(audience="requester")
    ensure_deliveries(envelope)
    if gate == "email_module":
        tenant.enabled_modules = [key for key in tenant.enabled_modules if key != "email"]
        tenant.save(update_fields=["enabled_modules"])
    elif gate == "personal":
        MemberNotificationPreference.objects.create(makerspace=tenant, user=member, feature="bookings", channel="email", enabled=False)
    else:
        EmailSuppression.objects.create(makerspace=tenant, address_hash=address_hash(tenant.pk, member.email), reason="complaint")
    # The personal worker reloads the queued envelope and all delivery gates.
    deliver_envelope(envelope.pk)
    assert envelope.deliveries.get(channel="email").state == "skipped"
    assert not restored_logs(tenant).filter(audience="requester", status="sent").exists()
    assert not send.called


def test_refused_undo_and_rolled_back_restore_emit_no_restored_event(
    monkeypatch, django_capture_on_commit_callbacks,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    resource.approval_mode = BookableSpace.ApprovalMode.APPROVE
    resource.save(update_fields=["approval_mode"])
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RestoreRefused):
            restore_booking(booking, actor=actor)
    assert not restored_envelopes(tenant).exists()
    assert not restored_logs(tenant).exists()
    resource.approval_mode = BookableSpace.ApprovalMode.INSTANT
    resource.save(update_fields=["approval_mode"])
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError, match="rollback restore"):
            with transaction.atomic():
                restore_booking(booking, actor=actor)
                raise RuntimeError("rollback restore")
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert not restored_envelopes(tenant).exists()
    assert not restored_logs(tenant).exists()
    assert not send.called


def enable_inbox(tenant):
    tenant.enabled_features = sorted(set(tenant.enabled_features) | {"notifications.member_inbox", "bookings.staff_grants"})
    tenant.save(update_fields=["enabled_features"])


def test_restored_email_uses_current_account_address_after_commit(monkeypatch, django_capture_on_commit_callbacks):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    old_email = booking.email
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        restore_booking(booking, actor=actor)
    member.email = "current-owner@example.test"
    member.save(update_fields=["email"])
    # Prove the new mailbox; an address edit cannot retain the old proof.
    assert member.email_verified_at is None
    member.email_verified_at = timezone.now()
    member.save(update_fields=["email_verified_at"])
    for callback in callbacks:
        callback()
    deliver_restored(tenant, audience="requester")
    log = restored_logs(tenant).get(audience="requester")
    assert log.to_email == member.email and log.to_email != old_email
    _deliver(log)
    assert log.status == "sent" and send.call_count == 1


def test_restored_email_refuses_an_unverified_changed_mailbox(monkeypatch, django_capture_on_commit_callbacks):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        restore_booking(booking, actor=actor)
    member.email = "unproven-owner@example.test"
    member.save(update_fields=["email"])
    assert member.email_verified_at is None
    for callback in callbacks:
        callback()
    deliver_restored(tenant, audience="requester")
    assert not restored_logs(tenant).filter(audience="requester").exists()
    assert send.call_count == 0


@pytest.mark.parametrize("gate", ["suspended", "revoked", "member_opt_out"])
def test_owner_becoming_ineligible_before_callback_suppresses_requester_only(
    monkeypatch, django_capture_on_commit_callbacks, gate,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    enable_inbox(tenant)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        restore_booking(booking, actor=actor)
    if gate == "suspended":
        member.access_status = "suspended"
        member.save(update_fields=["access_status"])
    else:
        values = {"status": "revoked"} if gate == "revoked" else {"receives_notifications": False}
        MakerspaceMembership.objects.filter(makerspace=tenant, user=member).update(**values)
    for callback in callbacks:
        callback()
    deliver_restored(tenant)
    assert list(restored_logs(tenant).values_list("audience", flat=True)) == ["staff"]
    assert not NotificationInboxRow.objects.filter(makerspace=tenant, user=member, event="restored").exists()
    assert NotificationInboxRow.objects.filter(makerspace=tenant, user=actor, event="restored").exists()


@pytest.mark.parametrize("gate", ["enabled", "module", "feature", "personal", "matrix"])
def test_requester_restored_inbox_preserves_existing_module_and_preference_gates(
    monkeypatch, django_capture_on_commit_callbacks, gate,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    enable_inbox(tenant)
    if gate == "module":
        tenant.enabled_modules.remove("notifications")
        tenant.save(update_fields=["enabled_modules"])
    elif gate == "feature":
        tenant.enabled_features.remove("notifications.member_inbox")
        tenant.save(update_fields=["enabled_features"])
    elif gate == "personal":
        MemberNotificationPreference.objects.create(makerspace=tenant, user=member, feature="bookings", channel="in_app", enabled=False)
    elif gate == "matrix":
        NotificationPreference.objects.create(makerspace=tenant, feature="bookings", channel="in_app", enabled=False)
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    deliver_restored(tenant)
    rows = NotificationInboxRow.objects.filter(makerspace=tenant, user=member, event="restored")
    assert rows.exists() is (gate == "enabled")
    if gate == "enabled":
        assert "Status: confirmed" in rows.get().summary
        assert "cancellation was undone" in rows.get().summary
        assert bookings_context(booking, "restored")["booking"].when in rows.get().summary


@pytest.mark.parametrize("permission", ["manage_reservations", "check_in"])
def test_restored_staff_wording_reaches_only_reservation_grants(
    monkeypatch, django_capture_on_commit_callbacks, permission,
):
    tenant, actor, member, resource, booking, send, message = cancelled(monkeypatch)
    enable_inbox(tenant)
    grantee, _ = _member(tenant, "restore-grant-only")
    BookingSpaceStaffGrant.objects.create(makerspace=tenant, space=resource, user=grantee,
                                          granted_by=actor, permissions=[permission])
    with django_capture_on_commit_callbacks(execute=True):
        restore_booking(booking, actor=actor)
    deliver_restored(tenant)
    assert set(restored_logs(tenant).values_list("to_email", flat=True)) == {member.email, actor.email}
    rows = NotificationInboxRow.objects.filter(makerspace=tenant, user=grantee, event="restored")
    assert rows.exists() is (permission == "manage_reservations")
    if permission == "manage_reservations":
        envelope = restored_envelopes(tenant).get(recipient=grantee)
        assert envelope.source_kind == "bookings.grant_alert" and envelope.audience == "member"
        from apps.integrations.notification_sources import render
        assert render(envelope)["text"] == render(restored_envelopes(tenant).get(recipient=actor))["text"]
