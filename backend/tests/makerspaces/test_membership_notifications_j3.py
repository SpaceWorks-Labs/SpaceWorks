from unittest.mock import Mock

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from tests.notification_delivery_helpers import run_outbox

import pytest
from django.utils import timezone

from tests.accounts.account_factories import make_staff

from apps.accounts.models import User
from apps.integrations import notify
from apps.integrations.models import (
    EmailLog,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationFeature,
    NotificationPreference,
)
from apps.makerspaces import membership_notifications, membership_services
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


pytestmark = pytest.mark.django_db


def _user(username):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="password",
    )
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def _space(slug, **kwargs):
    return Makerspace.objects.create(name=slug, slug=slug, **kwargs)


def _role(makerspace, slug):
    return MakerspaceRole.objects.get(makerspace=makerspace, slug=slug)


def _manager(makerspace, username="manager"):
    return make_staff(makerspace, username=username, email=f"{username}@example.test",
                      password="password", email_verified_at=timezone.now())


def test_open_join_sends_member_welcome_email_without_staff_channel_fanout(
    monkeypatch, settings, mailoutbox, django_capture_on_commit_callbacks,
):
    run_outbox(monkeypatch, settings)
    makerspace = _space("member-welcome", membership_policy=Makerspace.MembershipPolicy.OPEN)
    member = _user("member-welcome-user")
    with django_capture_on_commit_callbacks(execute=True):
        outcome = membership_services.request_membership(member, makerspace)
        assert not mailoutbox
        own = NotificationEnvelope.objects.get(recipient=member, event="joined")
        assert own.source_kind == "membership.lifecycle" and own.audience == "requester"
        assert not NotificationEnvelope.objects.filter(event="joined", audience="staff").exists()
    assert outcome["outcome"] == "joined"
    assert NotificationFeature.MEMBERS == "members"
    assert [message.to for message in mailoutbox] == [[member.email]]
    log = EmailLog.objects.get(event="joined")
    assert (log.stream, log.audience, log.recipient_id) == ("membership", "member", member.pk)


def test_activation_is_idempotent_and_does_not_duplicate_member_delivery(
    monkeypatch, settings, mailoutbox, django_capture_on_commit_callbacks,
):
    run_outbox(monkeypatch, settings)
    makerspace = _space("member-idempotent", membership_policy=Makerspace.MembershipPolicy.OPEN)
    member = _user("member-idempotent-user")
    with django_capture_on_commit_callbacks(execute=True):
        first = membership_services.request_membership(member, makerspace)
        second = membership_services.request_membership(member, makerspace)
    assert first["membership_id"] == second["membership_id"]
    assert NotificationEnvelope.objects.filter(recipient=member, event="joined").count() == 1
    assert [message.to for message in mailoutbox] == [[member.email]]


def test_request_policy_emits_the_pending_staff_lifecycle_event(monkeypatch):
    makerspace = _space("member-request-pending")
    manager = _manager(makerspace, "pending-manager")
    applicant = _user("member-request-applicant")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    outcome = membership_services.request_membership(applicant, makerspace)
    assert outcome["outcome"] == "requested"
    envelope = NotificationEnvelope.objects.get(recipient=manager, audience="staff", event="request_pending")
    assert envelope.feature == "members" and envelope.source_kind == "membership.application"
    assert envelope.source_id == str(outcome["request_id"])


def test_verification_sends_a_member_only_email_once(
    monkeypatch, settings, mailoutbox, django_capture_on_commit_callbacks,
):
    run_outbox(monkeypatch, settings)
    makerspace = _space("member-verified")
    manager = _manager(makerspace)
    member = _user("member-verified-user")
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=member, assigned_role=_role(makerspace, "member"),
        role=MakerspaceMembership.Role.CUSTOM,
    )
    with django_capture_on_commit_callbacks(execute=True):
        membership_services.verify_member(manager, membership)
        membership_services.verify_member(manager, membership)
        assert not mailoutbox
    assert [message.to for message in mailoutbox] == [[member.email]]
    assert NotificationEnvelope.objects.filter(event="verified").count() == 1
    assert not NotificationEnvelope.objects.filter(event="verified", audience="staff").exists()
    log = EmailLog.objects.get(event="verified")
    assert (log.stream, log.audience, log.recipient_id) == ("membership", "member", member.pk)


def test_member_staff_alerts_follow_the_matrix_and_makerspace_scope(
    monkeypatch, django_capture_on_commit_callbacks,
):
    from tests.test_notification_families_f3 import capture_delivery
    from apps.integrations.notification_tasks import deliver_envelope
    makerspace = _space("member-staff-alerts")
    manager = _manager(makerspace, "member-staff-manager")
    other_manager = _manager(_space("member-other-space"), "member-other-manager")
    member = _user("member-staff-target")
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=member, assigned_role=_role(makerspace, "member"),
        role=MakerspaceMembership.Role.CUSTOM, activated_by=manager,
    )
    emails, channels = capture_delivery(monkeypatch)
    # One durable edge: preferences are rechecked before its one delivery.
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    membership_notifications.notify_member_joined(membership, sync=True)
    envelope = NotificationEnvelope.objects.get(event="member_joined", recipient=manager)
    assert [target.channel for target in resolve(envelope)] == []
    assert not NotificationEnvelope.objects.filter(recipient=other_manager).exists()
    NotificationPreference.objects.create(makerspace=makerspace, feature="members", channel="email", enabled=True)
    assert [target.channel for target in resolve(envelope)] == ["email"]
    with django_capture_on_commit_callbacks(execute=True):
        deliver_envelope.run(envelope.pk)
    assert [call["to_email"] for call in emails] == [manager.email]
    assert other_manager.email not in [call["to_email"] for call in emails]
    assert channels == []
    NotificationPreference.objects.filter(makerspace=makerspace, feature="members", channel="email").update(enabled=False)
    NotificationPreference.objects.create(makerspace=makerspace, feature="members", channel="telegram", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        membership_notifications.notify_member_joined(membership, sync=True)
    assert len(emails) == 1
    assert [call["channel"] for call in channels] == ["telegram"]


def test_legacy_manager_invitation_email_still_uses_the_membership_stream(monkeypatch):
    makerspace = _space("member-invitation")
    manager = _manager(makerspace)
    email = Mock()
    monkeypatch.setattr("apps.integrations.email.send_makerspace_email", email)

    membership_services.invite_membership(
        manager, makerspace, "invitee@example.test", _role(makerspace, "member")
    )

    email.assert_called_once()
    assert email.call_args.args[3] == ["invitee@example.test"]
    assert email.call_args.kwargs == {
        "stream": "membership", "event": "invitation", "audience": "member",
    }
