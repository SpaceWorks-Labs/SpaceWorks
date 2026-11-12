from datetime import timedelta

import pytest
from apps.makerspaces.models import MakerspaceMembership
from django.utils import timezone

from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.makerspaces.models import MembershipRequest, MembershipVouch
from apps.makerspaces.notifications_p2_broadcasts import notify_broadcast
from apps.makerspaces.notifications_p2_vouches import notify_vouch
from apps.notifications.models_broadcasts import MemberBroadcast

pytestmark = pytest.mark.django_db


def test_member_broadcast_uses_live_segment_and_original_authority(lane):
    broadcast = MemberBroadcast.objects.create(makerspace=lane.space, created_by=lane.manager,
        title="Workshop update", body="Private member announcement")
    notify_broadcast(broadcast, user_id=lane.owner.pk, segment={})
    envelope = lane.deliver("broadcast")
    assert source_eligible(envelope)
    # Outbound chat bodies now carry the canonical navigation link after the message.
    assert lane.fake.calls[-1][1]["text"].startswith("Private member announcement")
    assert envelope.audience == "requester"
    MakerspaceMembership.all_tracks.filter(user=lane.manager).update(status="revoked")
    assert resolve(envelope) == []


def test_campaign_rechecks_changed_audience(lane):
    broadcast = MemberBroadcast.objects.create(makerspace=lane.space, created_by=lane.manager,
        title="Update", body="Member body")
    notify_broadcast(broadcast, user_id=lane.owner.pk, segment={})
    lane.membership.status = "revoked"
    lane.membership.save(update_fields=["status"])
    from apps.integrations.models_contract import NotificationEnvelope
    assert resolve(NotificationEnvelope.objects.get()) == []


def test_vouch_is_explicit_and_disappears_when_voucher_authority_expires(lane):
    policy = lane.space.admission_settings
    policy.configured = True
    policy.join_mode = "vouch"
    policy.voucher_min_tenure_days = 0
    policy.save()
    row = MembershipRequest.objects.create(makerspace=lane.space, user=lane.owner,
        kind="request", state="awaiting_vouches", expires_at=timezone.now()+timedelta(days=5))
    # Vouching is a community-track act (valid_vouches reads community memberships), so the voucher is a member,
    # not the staff-track manager (decision 63: one account per person, staff authority lives on the staff track).
    voucher = lane.account("p2-voucher", "member")
    vouch = MembershipVouch.objects.create(makerspace=lane.space, request=row, voucher=voucher,
        expires_at=timezone.now()+timedelta(days=5))
    notify_vouch(vouch)
    envelope = lane.deliver("vouched")
    assert source_eligible(envelope)
    assert voucher.username not in lane.fake.calls[-1][1]["text"]
    MakerspaceMembership.all_tracks.filter(user=voucher).update(status="revoked")
    assert not source_eligible(envelope)
