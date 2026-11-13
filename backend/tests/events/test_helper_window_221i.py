"""Decision 221(i): a co-organizer limited to a track/window appoints helpers inside it, never wider."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.contributions.authority import inherited_window
from apps.events.contributions.models_roles import EventGrantEntitlement
from tests.events.test_decision15_coorganizer_journeys import REFUSED, event_tracks, granted, world  # noqa: F401

pytestmark = pytest.mark.django_db


def limited(w, **fields):
    event_tracks(w.event)
    user, grant = granted(w.event, w.manager, ["judge", "manage_team"], name="limited")
    EventGrantEntitlement.objects.filter(grant=grant, revoked_at__isnull=True).update(**fields)
    return user


def test_time_boxed_co_organizer_helpers_inherit_the_same_window():
    w = world("w221i")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, valid_until=end)
    start, until = inherited_window(actor=boxed, target=w.event, permissions=("judge",))
    assert start is None and until == end


def test_unwindowed_co_organizer_and_managers_delegate_without_a_window():
    w = world("w221i-free")
    assert inherited_window(actor=w.co, target=w.event, permissions=("judge",)) == (None, None)
    assert inherited_window(actor=w.manager, target=w.event, permissions=("judge",)) == (None, None)


def test_track_limited_source_cannot_cover_a_wider_or_other_track():
    from apps.events.contracts.services import DelegationScope
    from apps.events.contributions.authority import can_delegate_helpers
    w = world("w221i-track")
    scoped = limited(w, track_ids=[7])
    ok = DelegationScope(event_id=w.event.pk, helper_role="judge", track_ids=(7,))
    assert can_delegate_helpers(actor=scoped, target=w.event, permissions=["judge"], scope=ok)
    for tracks in ((), (7, 8), (8,)):
        wider = DelegationScope(event_id=w.event.pk, helper_role="judge", track_ids=tracks)
        assert not can_delegate_helpers(actor=scoped, target=w.event, permissions=["judge"], scope=wider)


def test_window_wider_than_the_source_is_refused():
    from apps.events.contracts.services import DelegationScope
    from apps.events.contributions.authority import can_delegate_helpers
    w = world("w221i-wide")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, valid_until=end)
    same = DelegationScope(event_id=w.event.pk, helper_role="judge", valid_until=end)
    wider = DelegationScope(event_id=w.event.pk, helper_role="judge", valid_until=end + timedelta(hours=1))
    unbounded = DelegationScope(event_id=w.event.pk, helper_role="judge")
    assert can_delegate_helpers(actor=boxed, target=w.event, permissions=["judge"], scope=same)
    assert not can_delegate_helpers(actor=boxed, target=w.event, permissions=["judge"], scope=wider)
    assert not can_delegate_helpers(actor=boxed, target=w.event, permissions=["judge"], scope=unbounded)


# Staff-grant invitations carry the inviter's track/window limit (decision 221(i)).

def test_a_limited_co_organizers_invite_inherits_and_acceptance_keeps_the_limit():
    from apps.events import event_authority, services_staff_grants as services
    from tests.events.test_decision15_coorganizer_journeys import person
    w = world("w221i-invite")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, track_ids=[7], valid_until=end)
    invite, token = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7])
    assert (invite.track_ids, invite.valid_from, invite.valid_until) == ([7], None, end)
    helper = person("limited-helper")
    grant = services.redeem_invite(token, actor=helper)
    source = EventGrantEntitlement.objects.get(grant=grant, source_kind="manual", revoked_at__isnull=True)
    assert (source.track_ids, source.valid_until) == ([7], end)
    assert event_authority.can(helper, w.event, "judge", track_id=7)
    assert not event_authority.can(helper, w.event, "judge")  # never event-wide


def test_a_narrower_window_is_allowed_and_a_wider_one_or_other_track_is_refused():
    from apps.events import services_staff_grants as services
    w = world("w221i-wider")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(w, track_ids=[7], valid_until=end)
    narrower, _ = services.create_invite(w.event, actor=boxed, permissions=["judge"], track_ids=[7],
                                         valid_until=end - timedelta(hours=1))
    assert narrower.valid_until == end - timedelta(hours=1)
    for wider in ({"valid_until": end + timedelta(hours=1)}, {"track_ids": [8]}, {"track_ids": [7, 8]}):
        with pytest.raises(REFUSED):
            services.create_invite(w.event, actor=boxed, permissions=["judge"], **{"track_ids": [7], **wider})


def test_a_manager_invite_without_limits_stays_unlimited_and_the_invite_serializer_shows_limits():
    from apps.events import services_staff_grants as services
    from apps.events.serializers_staff_grants import StaffGrantInviteSerializer
    w = world("w221i-manager")
    invite, _ = services.create_invite(w.event, actor=w.manager, permissions=["judge"])
    assert (invite.track_ids, invite.valid_from, invite.valid_until) == ([], None, None)
    assert {"track_ids", "valid_from", "valid_until"} <= set(StaffGrantInviteSerializer(invite).data)
