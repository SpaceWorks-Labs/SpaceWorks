"""Staff RBAC mail survives membership-off; community mail remains gated."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from tests.account_split.p1_helpers import staff as make_staff

from apps.accounts.models import User
from apps.integrations.dispatch import _deliver
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_direct_mail import prepare
from apps.integrations.notification_resolution import eligible, resolve
from apps.integrations.notification_tasks import deliver_envelope
from apps.makerspaces import membership_services
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from apps.makerspaces.notifications_p2_members import notify_invitation, notify_member

pytestmark = pytest.mark.django_db


def membership_off(space):
    space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
    space.save(update_fields=["enabled_modules"])


def invited(world, role="inventory_manager", *, member_account=False):
    # Historical notice rows remain readable; they never confer staff authority.
    fields = {"email": "invitee@example.test", "email_verified_at": timezone.now()}
    if role == "member" or member_account:
        user = User.objects.create_user(username="invitee", **fields)
    else:
        user, _ = make_staff(world.space, "invitee", role=role, **fields)
    row = MembershipRequest.objects.create(makerspace=world.space, user=user, invite_email=user.email,
        kind="invite", state="invited", invited_by=world.staff, assigned_role=world.space.roles.get(slug=role),
        expires_at=timezone.now() + timedelta(days=1))
    return row


def test_legacy_staff_invitation_refuses_existing_member_without_sending_mail(world, mailoutbox):
    membership_off(world.space)
    target = User.objects.create_user(username="new-staff", email="new-staff@example.test", email_verified_at=timezone.now())
    with pytest.raises(ValidationError):
        membership_services.invite_membership(world.staff, world.space, target.email,
                                             world.space.roles.get(slug="inventory_manager"))
    target.refresh_from_db()
    assert target.account_kind == "member" and target.staff_makerspace_id is None
    assert not target.makerspace_memberships.exists()
    assert not MembershipRequest.objects.filter(user=target).exists()
    assert not NotificationEnvelope.objects.filter(recipient=target).exists()
    assert not EmailLog.objects.filter(to_email=target.email).exists()
    assert not mailoutbox


@pytest.mark.parametrize("event", ["joined", "approved"])
def test_staff_activation_welcome_is_account_mail(world, event, django_capture_on_commit_callbacks, mailoutbox):
    membership_off(world.space)
    user, row = make_staff(world.space, "activated-staff", role="inventory_manager",
                           email="active@example.test", email_verified_at=timezone.now())
    row.activated_by, row.activated_at = world.staff, timezone.now()
    row.save(update_fields=["activated_by", "activated_at"])
    with django_capture_on_commit_callbacks(execute=True):
        notify_member(row, event, staff=False)
        notify_member(row, event, staff=False)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.lifecycle", recipient=user)
    assert (envelope.feature, envelope.stream) == ("", "account") and eligible(envelope)
    log = EmailLog.objects.get(source_kind="notification.direct", source_id=envelope.pk)
    assert prepare(log)
    _deliver(log)
    assert log.status == "sent" and len(mailoutbox) == 1
    deliver_envelope(envelope.pk)
    assert EmailLog.objects.filter(source_id=envelope.pk, to_email=user.email).count() == 1


def test_community_invitation_keeps_membership_gate(world, django_capture_on_commit_callbacks):
    row = invited(world, "member")
    membership_off(world.space)
    with django_capture_on_commit_callbacks(execute=True):
        notify_invitation(row)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.application", recipient=row.user)
    assert (envelope.feature, envelope.stream) == ("members", "membership")
    assert not eligible(envelope)
    assert not EmailLog.objects.filter(to_email=row.user.email).exists()


def test_routed_email_suppresses_compatibility_copy(world, django_capture_on_commit_callbacks, mailoutbox):
    membership_off(world.space)
    row = invited(world)
    # Exercise the resolver owning email, rather than the compatibility fallback.
    NotificationPreference.objects.create(makerspace=world.space, feature="", channel="email", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify_invitation(row)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.application", recipient=row.user)
    assert any(target.channel == "email" for target in resolve(envelope))
    assert not EmailLog.objects.filter(to_email=row.user.email).exists()
    deliver_envelope(envelope.pk)
    with django_capture_on_commit_callbacks(execute=True):
        notify_invitation(row)
    deliver_envelope(envelope.pk)
    assert EmailLog.objects.filter(to_email=row.user.email, status="sent").count() == 1
    assert not EmailLog.objects.filter(source_kind="notification.direct", source_id=envelope.pk).exists()
    assert len(mailoutbox) == 1


def test_separate_staff_account_keeps_existing_members_staff_summary(world):
    # The same person receives staff mail on their separate staff principal.
    owner_account, row = make_staff(world.space, "owner-staff", role="inventory_manager",
                                    email=world.owner.email)
    row.activated_by, row.activated_at = world.staff, timezone.now()
    row.save(update_fields=["activated_by", "activated_at"])
    notify_member(row, "approved")
    owner = NotificationEnvelope.objects.get(source_kind="membership.lifecycle", recipient=owner_account)
    staff = NotificationEnvelope.objects.get(source_kind="membership.lifecycle", recipient=world.staff)
    assert (owner.feature, owner.stream) == ("", "account")
    assert (staff.feature, staff.stream) == ("members", "membership")
    world.owner.refresh_from_db()
    assert world.owner.account_kind == "member"
    assert world.owner.makerspace_memberships.get(makerspace=world.space).assigned_role.slug == "member"
    assert not NotificationEnvelope.objects.filter(source_kind="membership.lifecycle", recipient=world.owner).exists()


def test_legacy_staff_approval_refuses_member_without_sending_welcome(world, mailoutbox):
    membership_off(world.space)
    row = invited(world, member_account=True)
    with pytest.raises(ValidationError):
        membership_services.approve_request(world.staff, row, row.assigned_role)
    row.refresh_from_db()
    row.user.refresh_from_db()
    assert row.state == "invited" and row.user.account_kind == "member"
    assert not MakerspaceMembership.objects.filter(user=row.user).exists()
    assert not NotificationEnvelope.objects.filter(source_kind="membership.lifecycle", recipient=row.user).exists()
    assert not EmailLog.objects.filter(to_email=row.user.email).exists()
    assert not mailoutbox


def test_dedicated_staff_invitation_already_uses_core_account_stream(world, mailoutbox):
    from apps.accounts.staff_invitation_delivery import deliver
    membership_off(world.space)
    invitation = SimpleNamespace(pk=42, makerspace=world.space, email="staff@example.test",
        role=world.space.roles.get(slug="inventory_manager"), expires_at=timezone.now() + timedelta(days=1))
    result = deliver(invitation, "test-only-bearer")
    assert result["delivery_status"] == "sent" and len(mailoutbox) == 1
    log = EmailLog.objects.get(to_email=invitation.email)
    assert (log.stream, log.event) == ("account", "staff_invitation")
    assert not log.text_body  # The invitation bearer stays out of durable mail logs.


@pytest.mark.parametrize("change", ["community", "revoked", "expired", "sender_revoked", "email_off"])
def test_staff_invitation_revalidates_before_compatibility_delivery(world, change, django_capture_on_commit_callbacks):
    membership_off(world.space)
    row = invited(world)
    with django_capture_on_commit_callbacks(execute=True):
        notify_invitation(row)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.application", recipient=row.user)
    log = EmailLog.objects.get(source_kind="notification.direct", source_id=envelope.pk)
    if change == "community":
        # Do not change the revision: live role classification must still reject it.
        MembershipRequest.objects.filter(pk=row.pk).update(assigned_role=world.space.roles.get(slug="member"))
    elif change == "revoked":
        MembershipRequest.objects.filter(pk=row.pk).update(state="revoked")
    elif change == "expired":
        MembershipRequest.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    elif change == "sender_revoked":
        world.staff.is_active = False
        world.staff.save(update_fields=["is_active"])
    else:
        world.space.enabled_modules.remove("email")
        world.space.save(update_fields=["enabled_modules"])
    _deliver(log)
    assert log.status == "skipped"
