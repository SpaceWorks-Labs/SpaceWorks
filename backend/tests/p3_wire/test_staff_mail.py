import pytest
from django.utils import timezone

from apps.integrations.notification_resolution import email_eligible
from apps.makerspaces.models import MakerspaceMembership

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("feature,source", [("events", "events.lifecycle"), ("bookings", "bookings.lifecycle"),
    ("hardware_requests", "hardware.request"), ("hardware_requests", "hardware.loan_reminder"),
    ("hardware_requests", "hardware.problem_report"), ("hardware_requests", "hardware.charge"),
    ("printing", "machines.service"), ("maintenance", "machines.maintenance"), ("stock", "machines.procurement"),
    ("certifications", "machines.certification"), ("certifications", "machines.certification_summary")])
def test_unverified_active_tenant_staff_keeps_operational_email(world, feature, source):
    envelope = world.envelope(user=world.staff, feature=feature, stream=feature, source_kind=source, audience="staff")
    assert world.staff.email_verified_at is None and email_eligible(envelope)


@pytest.mark.parametrize("audience", ["member", "requester"])
def test_staff_role_does_not_relax_requester_or_member_email(world, audience):
    envelope = world.envelope(user=world.staff, audience=audience)
    assert not email_eligible(envelope)


@pytest.mark.parametrize("source", ["events.broadcast", "bookings.broadcast", "membership.broadcast", "contract.test"])
def test_staff_audience_does_not_relax_campaign_or_unknown_source_email(world, source):
    envelope = world.envelope(user=world.staff, audience="staff", source_kind=source, event="broadcast")
    assert not email_eligible(envelope)


@pytest.mark.parametrize("withdrawal", ["revoked", "opted_out", "inactive", "restricted", "foreign", "member_account"])
def test_unverified_staff_allowance_requires_current_tenant_staff_authority(world, withdrawal):
    envelope = world.envelope(user=world.staff, audience="staff")
    # The staff authority is the staff-track row (one account per person); the default manager is community-only.
    membership = MakerspaceMembership.staff_tracks.get(user=world.staff, makerspace=world.space)
    assert email_eligible(envelope)
    if withdrawal == "revoked":
        membership.status = "revoked"
        membership.save(update_fields=["status"])
    elif withdrawal == "opted_out":
        membership.receives_notifications = False
        membership.save(update_fields=["receives_notifications"])
    elif withdrawal in ("inactive", "restricted"):
        setattr(world.staff, "is_active" if withdrawal == "inactive" else "access_status", False if withdrawal == "inactive" else "restricted")
        world.staff.save()
    elif withdrawal == "member_account":
        # A member can never be demoted from built-in staff: identity is immutable.
        # Even a staff-labelled operational envelope cannot relax member verification.
        envelope.recipient = world.owner
        envelope.save(update_fields=["recipient"])
    else:
        from apps.makerspaces.models import Makerspace
        envelope.makerspace = Makerspace.objects.create(name="Elsewhere", slug="p3-elsewhere")
        envelope.save(update_fields=["makerspace"])
    assert not email_eligible(envelope)


def test_staff_email_still_honors_email_opt_out(world):
    from apps.notifications.models_inbox import MemberNotificationPreference
    envelope = world.envelope(user=world.staff, audience="staff")
    MemberNotificationPreference.objects.create(makerspace=world.space, user=world.staff,
                                                feature="bookings", channel="email", enabled=False)
    assert not email_eligible(envelope)


def test_verified_member_email_behavior_is_unchanged(world):
    world.owner.email_verified_at = timezone.now()
    world.owner.save(update_fields=["email_verified_at"])
    assert email_eligible(world.envelope(user=world.owner))
