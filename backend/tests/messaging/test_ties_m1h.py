"""Tenant ownership admits account-only recipients without changing inbox selection."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from apps.integrations.messaging.consent import grant_consent
from apps.integrations.messaging.ties import has_tenant_tie
from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_addressed import eligible
from apps.integrations.notify import LifecyclePayload
from apps.integrations.recipients_addressed import addressed_recipients
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.notifications.inbox import InboxDelivery
from tests.messaging.canonical_helpers import (
    envelope, platform_sms, platform_whatsapp, sms_channel, verified_endpoint, whatsapp_channel,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def senders(space):
    """Canonical platform senders the tenant explicitly opted in to (D1)."""
    platform_sms()
    platform_whatsapp()
    return {"sms": sms_channel(space), "whatsapp": whatsapp_channel(space)}


def addressed(space, user, channel="sms", key="ties"):
    """Delivery-time addressed eligibility on the canonical envelope pipeline."""
    endpoint = NotificationEndpoint.objects.filter(makerspace=space, user=user, channel="whatsapp",
                                                   revoked_at=None).first() if channel == "whatsapp" else None
    return eligible(envelope(space, user, key=key), channel, endpoint)


def payload_for(request):
    return LifecyclePayload(text="Staff wording", data={"request_id": request.pk},
        inbox=(InboxDelivery(request.requester_id, "Your request", "Member wording"),))


def assert_can_opt_in(client, user, space, channel="sms"):
    client.force_authenticate(user)
    assert client.get(reverse("member-messaging"), {"makerspace": space.pk}).status_code == 200
    response = client.post(reverse("member-messaging-consent"), {
        "makerspace": space.pk, "channel": channel, "action": "opted_in",
    }, format="json")
    assert response.status_code == 200
    assert response.data[channel]["consented"]


@pytest.fixture
def borrower(space, member):
    # Establish ownership BEFORE removing membership and granting consent.
    HardwareRequest.objects.create(makerspace=space, requester=member, requester_username=member.username)
    MakerspaceMembership.objects.filter(makerspace=space, user=member).delete()
    return member


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_account_only_borrower_opts_in_and_receives(space, borrower, client, senders, channel):
    assert not addressed(space, borrower, channel, key="before")
    if channel == "whatsapp":
        verified_endpoint(borrower, senders["whatsapp"])  # Signed proof, never SMS consent.
    assert_can_opt_in(client, borrower, space, channel)
    assert addressed(space, borrower, channel, key="after")


@pytest.mark.parametrize("kind", ["booking", "registration"])
def test_booking_or_registration_alone_admits_consent(space, member, client, kind):
    MakerspaceMembership.objects.filter(makerspace=space, user=member).delete()
    now = timezone.now()
    if kind == "booking":
        from apps.bookings.models import BookableSpace, Booking
        resource = BookableSpace.objects.create(makerspace=space, name="Bench")
        Booking.objects.create(space=resource, member=member, name="Owner", email="owner@example.test",
                               phone="123", starts_at=now, ends_at=now + timedelta(hours=1))
    else:
        from apps.events.models import Event, EventRegistration
        event = Event.objects.create(makerspace=space, title="Workshop", starts_at=now,
                                     ends_at=now + timedelta(hours=1))
        EventRegistration.objects.create(event=event, member=member, name="Owner",
                                         email="owner@example.test", phone="123")
    assert has_tenant_tie(member, space)
    assert_can_opt_in(client, member, space)


def test_revoked_member_with_old_loan_gets_uniform_404_and_delivery_skip(space, member, client):
    HardwareRequest.objects.create(makerspace=space, requester=member, requester_username=member.username)
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert addressed(space, member, key="before")
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(status="revoked")
    client.force_authenticate(member)
    denied = client.get(reverse("member-messaging"), {"makerspace": space.pk})
    missing = client.get(reverse("member-messaging"), {"makerspace": space.pk + 999999})
    assert denied.status_code == missing.status_code == 404 and denied.data == missing.data
    response = client.post(reverse("member-messaging-consent"), {
        "makerspace": space.pk, "channel": "sms", "action": "opted_in",
    }, format="json")
    assert response.status_code == 404
    assert not has_tenant_tie(member, space)
    assert not addressed(space, member, key="after")  # Revocation wins at delivery.


def test_tie_lost_after_enqueue_is_checked_at_delivery(space, borrower):
    grant_consent(user=borrower, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert addressed(space, borrower, key="before")
    HardwareRequest.objects.filter(makerspace=space, requester=borrower).delete()
    assert not has_tenant_tie(borrower, space)  # Retained consent is not a tie.
    assert not addressed(space, borrower, key="after")


@pytest.mark.parametrize("changes", [
    {"is_active": False}, {"access_status": "restricted"}, {"access_status": "suspended"},
    {"deletion_requested_at": timezone.now()}, {"is_tenant_dump_stub": True},
])
def test_account_exclusions_win_over_membership_and_owned_rows(space, member, client, changes):
    HardwareRequest.objects.create(makerspace=space, requester=member, requester_username=member.username)
    User.objects.filter(pk=member.pk).update(**changes)
    member.refresh_from_db()
    assert not has_tenant_tie(member, space)
    client.force_authenticate(member)
    assert client.get(reverse("member-messaging"), {"makerspace": space.pk}).status_code == 404
    assert client.post(reverse("member-messaging-consent"), {
        "makerspace": space.pk, "channel": "sms", "action": "opted_in",
    }, format="json").status_code == 404


@pytest.mark.parametrize("changes", [{"is_superuser": True}, {"role": "superadmin"}])
def test_member_accounts_cannot_hold_platform_authority(space, member, client, changes):
    # Account kinds are immutable: the database refuses platform flags on a member
    # account, and a real platform account has no member tie or member surface.
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=member.pk).update(**changes)
    root = User.objects.create_superuser(username="ties-root", password="test-password")
    assert not has_tenant_tie(root, space)
    client.force_authenticate(root)
    assert client.get(reverse("member-messaging"), {"makerspace": space.pk}).status_code == 404


def test_tie_never_matches_contact_text_or_a_different_tenant(space, borrower, client):
    other = Makerspace.objects.create(name="Other lab", slug="other-ties")
    assert not has_tenant_tie(borrower, other)
    # Contact snapshots name the borrower, but the authenticated owner is someone else.
    owner = User.objects.create_user(username="real-owner")
    HardwareRequest.objects.create(makerspace=other, requester=owner, requester_username=borrower.username,
                                   requester_contact_email=borrower.email, requester_contact_phone=borrower.phone_e164)
    assert not has_tenant_tie(borrower, other)
    client.force_authenticate(borrower)
    assert client.get(reverse("member-messaging"), {"makerspace": other.pk}).status_code == 404


def test_membership_notification_optout_still_wins_at_delivery(space, member):
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(receives_notifications=False)
    assert has_tenant_tie(member, space)
    # Managing consent is still possible; it cannot override membership opt-out.
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert not addressed(space, member)
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(receives_notifications=True)
    assert addressed(space, member, key="opted-back-in")


def test_account_only_inbox_recipients_and_wording_are_unchanged(space, borrower):
    from apps.notifications.inbox import eligible_owner, write_matrix_inbox
    from apps.notifications.models import NotificationInboxRow

    payload = payload_for(HardwareRequest.objects.get(makerspace=space, requester=borrower))
    assert eligible_owner(space, borrower.pk)
    assert (borrower.pk, "member") in addressed_recipients(space, "hardware_requests", "accepted", payload)
    space.enabled_features = [*space.enabled_features, "notifications.member_inbox"]
    space.save(update_fields=["enabled_features"])
    write_matrix_inbox(space, "hardware_requests", "accepted", payload, uuid4())
    row = NotificationInboxRow.objects.get(makerspace=space, user=borrower)
    assert (row.audience, row.title, row.summary) == ("member", "Your request", "Member wording")


def test_analytics_keeps_new_and_historical_skip_reasons(space, member):
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.reports_messaging import messaging_rows

    # Converted legacy skips keep their original reason on the canonical delivery.
    for reason in ("no_tenant_tie", "no_membership"):
        NotificationDelivery.objects.create(makerspace=space, envelope=envelope(space, member, key=reason),
            channel="sms", target_key="sms", provider="twilio", state="skipped", last_error=reason,
            historical=True)
    skips = {row["skip_reason"]: row["skipped_count"] for row in messaging_rows(space)
             if row["measurement"] == "delivery_cohort"}
    assert skips["no_tenant_tie"] == skips["no_membership"] == 1
