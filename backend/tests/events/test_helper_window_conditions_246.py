"""Decision 246: delegation limits (221i) across events, so a limit on one event never reaches another."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.contracts.services import DelegationScope
from apps.events.contributions.authority import can_delegate_helpers, inherited_window
from tests.events.test_helper_window_221i import limited
from tests.events.test_decision15_coorganizer_journeys import world

pytestmark = pytest.mark.django_db


def test_a_limited_co_organizer_of_one_event_cannot_delegate_on_another_event():
    first, second = world("w246-a"), world("w246-b")
    boxed = limited(first, track_ids=[7], valid_until=timezone.now() + timedelta(hours=2))
    own = DelegationScope(event_id=first.event.pk, helper_role="judge", track_ids=(7,),
                          valid_until=timezone.now() + timedelta(hours=1))
    foreign = DelegationScope(event_id=second.event.pk, helper_role="judge", track_ids=(7,),
                              valid_until=timezone.now() + timedelta(hours=1))
    assert can_delegate_helpers(actor=boxed, target=first.event, permissions=["judge"], scope=own)
    assert not can_delegate_helpers(actor=boxed, target=second.event, permissions=["judge"], scope=foreign)
    assert not can_delegate_helpers(actor=boxed, target=first.event, permissions=["judge"], scope=foreign)


def test_the_window_inherited_on_one_event_does_not_leak_to_another():
    first, second = world("w246-c"), world("w246-d")
    end = timezone.now() + timedelta(hours=2)
    boxed = limited(first, valid_until=end)
    assert inherited_window(actor=boxed, target=first.event, permissions=("judge",))[1] == end
    assert inherited_window(actor=boxed, target=second.event, permissions=("judge",)) != (None, end)


def test_a_permission_the_source_does_not_hold_cannot_be_delegated_and_the_check_is_repeatable():
    w = world("w246-perm")
    boxed = limited(w, valid_until=timezone.now() + timedelta(hours=2))
    scope = DelegationScope(event_id=w.event.pk, helper_role="judge")
    first = can_delegate_helpers(actor=boxed, target=w.event, permissions=["manage_money"], scope=scope)
    second = can_delegate_helpers(actor=boxed, target=w.event, permissions=["manage_money"], scope=scope)
    assert first is second is False
