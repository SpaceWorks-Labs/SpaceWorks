"""Decision 246 (lane F8): bad input and cross-space isolation for the events guest-pass adapter (223)."""
from datetime import timedelta

import pytest

from apps.events import guest_pass_adapter
from apps.events.models import Event
from apps.makerspaces.models import GuestPass
from tests.events.checkin_helpers import make_event, register
from tests.events.test_guest_pass_adapter_223 import _events_space
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("bad", [0, -1, 99999999, None, "abc"])
def test_an_unknown_or_malformed_registration_id_gives_no_pass_and_never_raises(bad):
    _events_space("f8-ga-bad")
    assert guest_pass_adapter.ensure_event_pass(bad) is None
    assert not GuestPass.objects.exists()


def test_a_registration_in_a_space_without_the_capability_gets_nothing_while_another_space_does():
    on, off = _events_space("f8-ga-on"), _events_space("f8-ga-off", adapter_on=False)
    guest = user("f8-ga-guest")
    in_off = register(make_event(off), guest)
    in_on = register(make_event(on), guest)
    assert guest_pass_adapter.ensure_event_pass(in_off.pk) is None
    row = guest_pass_adapter.ensure_event_pass(in_on.pk)
    assert row is not None and row.makerspace_id == on.pk
    assert not GuestPass.objects.filter(makerspace=off).exists()


def test_the_pass_lives_only_in_the_events_own_space_with_a_registration_scoped_key():
    first, second = _events_space("f8-ga-first"), _events_space("f8-ga-second")
    guest = user("f8-ga-both")
    reg_a = register(make_event(first), guest)
    reg_b = register(make_event(second), guest)
    pass_a = guest_pass_adapter.ensure_event_pass(reg_a.pk)
    pass_b = guest_pass_adapter.ensure_event_pass(reg_b.pk)
    assert pass_a.pk != pass_b.pk and (pass_a.makerspace_id, pass_b.makerspace_id) == (first.pk, second.pk)
    assert GuestPass.objects.filter(makerspace=first).count() == 1
    assert GuestPass.objects.filter(makerspace=second).count() == 1
    assert pass_a.operation_id == guest_pass_adapter.operation_id(reg_a.event_id, reg_a.pk)


def test_one_spaces_window_never_uses_another_spaces_return_hours():
    first, second = _events_space("f8-ga-w1"), _events_space("f8-ga-w2")
    guest = user("f8-ga-window")
    event_a = make_event(first, equipment_return_hours=24)
    event_b = make_event(second, equipment_return_hours=0)
    row_a = guest_pass_adapter.ensure_event_pass(register(event_a, guest).pk)
    row_b = guest_pass_adapter.ensure_event_pass(register(event_b, guest).pk)
    assert row_a.valid_until == event_a.ends_at + timedelta(hours=24)
    assert row_b.valid_until == event_b.ends_at


def test_a_completed_event_still_issues_and_a_cancelled_event_does_not():
    makerspace = _events_space("f8-ga-status")
    done = register(make_event(makerspace, status=Event.Status.COMPLETED), user("f8-ga-done"))
    assert guest_pass_adapter.ensure_event_pass(done.pk) is not None
    called_off = register(make_event(makerspace, status=Event.Status.CANCELLED), user("f8-ga-called-off"))
    assert guest_pass_adapter.ensure_event_pass(called_off.pk) is None
