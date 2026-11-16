from datetime import timedelta

import pytest
from apps.makerspaces.models import MakerspaceMembership
from django.db import transaction
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.makerspaces.membership_notifications import (
    notify_member_joined, notify_membership_request_pending, send_member_verified, send_member_welcome,
)
from apps.makerspaces.membership_notifications_research import notify_membership_decision
from apps.makerspaces.notifications_p2_members import notify_invitation, notify_request
from apps.makerspaces.models import MembershipRequest

pytestmark = pytest.mark.django_db


def application(lane, state="requested"):
    return MembershipRequest.objects.create(makerspace=lane.space, user=lane.owner,
        kind="request", state=state, requested_by=lane.owner, decided_by=lane.manager,
        invited_by=lane.manager, decided_at=timezone.now(), expires_at=timezone.now() + timedelta(days=5))


@pytest.mark.parametrize("event", ["request_pending", "member_joined", "approved", "joined", "verified"])
def test_lifecycle_rows_reach_only_live_explicit_recipients(lane, event):
    if event == "request_pending":
        notify_membership_request_pending(application(lane))
    elif event == "member_joined":
        notify_member_joined(lane.membership)
    elif event == "approved":
        notify_membership_decision(lane.membership, "approved")
    elif event == "joined":
        send_member_welcome(lane.membership, source="open")
    else:
        lane.membership.verified_at = timezone.now()
        lane.membership.verified_by = lane.manager
        lane.membership.save(update_fields=["verified_at", "verified_by"])
        from apps.audit.services import record
        record(lane.manager, "membership.verified", makerspace=lane.space, target=lane.membership)
        send_member_verified(lane.membership)
    recipient = lane.manager if event == "member_joined" else lane.owner
    envelope = lane.deliver(event, recipient)
    assert source_eligible(envelope)
    assert envelope.deliveries.get(channel="telegram").state == "accepted"
    if event in {"joined", "verified"}:
        assert not NotificationEnvelope.objects.filter(event=event, audience="staff").exists()


def test_approval_and_welcome_reserve_one_owner_intent(lane):
    notify_membership_decision(lane.membership, "approved")
    send_member_welcome(lane.membership, source="approval")
    assert NotificationEnvelope.objects.filter(recipient=lane.owner, event="approved").count() == 1


@pytest.mark.parametrize("event", ["declined", "awaiting_payment", "payment_due"])
def test_admission_rows_have_separate_owner_and_staff_bodies(lane, payment, event):
    row = application(lane, "revoked" if event == "declined" else "awaiting_payment")
    if event != "declined":
        # Use a real admission charge; it is distinct from the account-only loan fixture.
        from apps.payments.models import Payment
        row.admission_payment = Payment.objects.create(makerspace=lane.space, member=lane.owner,
            subject_type="membership_request", subject_id=row.pk, amount="25.00", currency="usd",
            provider="unclaimed", created_by=lane.manager)
        row.save(update_fields=["admission_payment"])
    notify_request(row, event)
    envelope = lane.deliver(event)
    assert source_eligible(envelope)
    assert NotificationEnvelope.objects.filter(event=event, recipient=lane.manager, audience="staff").exists()
    assert "Your membership" in lane.fake.calls[-1][1]["text"]


def test_membership_rollback_never_leaves_an_outbox_intent(lane):
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            notify_member_joined(lane.membership)
            assert NotificationEnvelope.objects.exists()
            raise RuntimeError("abort domain mutation")
    assert not NotificationEnvelope.objects.exists()


def test_withdrawn_verifier_authority_and_source_revision_block_retry(lane):
    lane.membership.verified_at = timezone.now()
    lane.membership.verified_by = lane.manager
    lane.membership.save(update_fields=["verified_at", "verified_by"])
    from apps.audit.services import record
    record(lane.manager, "membership.verified", makerspace=lane.space, target=lane.membership)
    send_member_verified(lane.membership)
    envelope = NotificationEnvelope.objects.get(recipient=lane.owner)
    MakerspaceMembership.all_tracks.filter(user=lane.manager).update(status="revoked")
    assert resolve(envelope) == []


def test_known_invitee_gets_no_room_bearer(lane):
    row = application(lane, "invited")
    notify_invitation(row)
    envelope = lane.deliver("invitation")
    assert source_eligible(envelope)
    assert "Sign in" in lane.fake.calls[-1][1]["text"]
    assert not NotificationEnvelope.objects.filter(event="invitation", audience="staff").exists()


def test_unknown_invitee_keeps_existing_email_path(lane, monkeypatch):
    row = application(lane, "invited")
    row.user = None
    row.invite_email = "external@example.test"
    row.save(update_fields=["user", "invite_email"])
    calls = []
    monkeypatch.setattr("apps.integrations.email.send_makerspace_email", lambda *a, **k: calls.append((a, k)))
    notify_invitation(row)
    assert calls[0][0][3] == ["external@example.test"]
    assert not NotificationEnvelope.objects.exists()


@pytest.mark.parametrize("verified_domain", [False, True])
def test_invitation_email_links_the_account_portal_invitations_section(lane, monkeypatch, settings, verified_domain):
    from apps.makerspaces.models import Makerspace
    settings.PUBLIC_APP_BASE_URL = "https://app.example"
    if verified_domain:  # single-tenant/custom domain: tenant-canonical URL has no /m/<slug>
        Makerspace.objects.filter(pk=lane.space.pk).update(
            frontend_domain="lab.example", frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
        lane.space.refresh_from_db()
    row = application(lane, "invited")
    row.user = None
    row.invite_email = "external@example.test"
    row.save(update_fields=["user", "invite_email"])
    row.makerspace.refresh_from_db()
    calls = []
    monkeypatch.setattr("apps.integrations.email.send_makerspace_email", lambda *a, **k: calls.append((a, k)))
    notify_invitation(row)
    expected = ("https://lab.example/member/account-portal?section=invitations" if verified_domain
                else f"https://app.example/m/{lane.space.slug}/member/account-portal?section=invitations")
    assert calls[0][0][2].endswith(f"Review it in your account: {expected}")


def test_known_invitee_inbox_link_opens_the_invitations_section(lane):
    from apps.makerspaces.notifications_p2_members import request_body
    row = application(lane, "invited")
    assert request_body(row, "invitation", "requester")["link"].endswith("/member/account-portal?section=invitations")


def test_failed_outbox_insert_cannot_poison_domain_transaction(lane, monkeypatch):
    def fail(**kwargs):
        from apps.accounts.models import User
        User.objects.create(username=lane.owner.username)  # Actual unique-constraint failure.
    monkeypatch.setattr("apps.operations.notifications_p2.emit", fail)
    with transaction.atomic():
        result = notify_member_joined(lane.membership)
        assert not result.scheduled
        # A real query in the same transaction remains usable.
        assert lane.space.memberships.filter(user=lane.owner).exists()


def test_pending_to_vouches_in_one_transaction_preserves_pending_notice(lane):
    row = application(lane)
    notify_membership_request_pending(row)
    row.state = "awaiting_vouches"
    row.save(update_fields=["state", "updated_at"])
    envelope = NotificationEnvelope.objects.get(recipient=lane.owner)
    assert source_eligible(envelope)


def test_repeat_verification_does_not_suppress_the_original_notice(lane):
    from apps.makerspaces.membership_verification import verify_member
    verify_member(lane.manager, lane.membership)
    verify_member(lane.manager, lane.membership)
    envelope = lane.deliver("verified")
    assert source_eligible(envelope)
    assert NotificationEnvelope.objects.filter(recipient=lane.owner, event="verified").count() == 1


def _direct_mail(event):
    from apps.integrations.models import EmailLog
    return EmailLog.objects.filter(event=event, source_metadata__has_key="p2_direct")


def test_welcome_keeps_direct_mail_once_while_members_email_cell_is_off(lane, django_capture_on_commit_callbacks):
    """Pre-Phase-2 welcome mail ignored the members matrix (email defaults OFF)."""
    with django_capture_on_commit_callbacks(execute=True):
        notify_membership_decision(lane.membership, "approved")
        send_member_welcome(lane.membership, source="approval")
    mail = _direct_mail("approved").get()
    assert mail.to_email == lane.owner.email and mail.subject == f"Welcome to {lane.space.name}"
    assert mail.recipient_id == lane.owner.pk
    # The envelope still carries the owner's selected chat.
    assert lane.deliver("approved").deliveries.get(channel="telegram").state == "accepted"


def test_welcome_direct_mail_yields_to_an_emailing_envelope(lane, django_capture_on_commit_callbacks):
    from apps.integrations.models import NotificationPreference as Matrix
    from apps.notifications.models_preferences import NotificationPreference
    Matrix.objects.create(makerspace=lane.space, feature="members", channel="email", enabled=True)
    NotificationPreference.objects.filter(user=lane.owner, category="members").update(channels=["telegram", "email"])
    with django_capture_on_commit_callbacks(execute=True):
        send_member_welcome(lane.membership, source="open")
    assert not _direct_mail("joined").exists()


def test_known_invitee_keeps_invitation_email(lane, django_capture_on_commit_callbacks):
    row = application(lane, "invited")
    row.invite_email = lane.owner.email
    row.save(update_fields=["invite_email"])
    with django_capture_on_commit_callbacks(execute=True):
        notify_invitation(row)
    mail = _direct_mail("invitation").get()
    assert mail.to_email == lane.owner.email and mail.subject == "Makerspace membership invitation"


def test_direct_mail_is_not_sent_when_the_domain_rolls_back(lane, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            send_member_welcome(lane.membership, source="open")
            raise RuntimeError("rollback")
    assert not callbacks and not _direct_mail("joined").exists()
