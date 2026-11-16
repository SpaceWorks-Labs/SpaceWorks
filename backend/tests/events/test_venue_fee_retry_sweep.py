"""EV-34 / A12: the scheduled pass that re-raises a venue fee whose first charge failed (audit B-9)."""

import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import tasks_recovery, venue_fees
from apps.events.models import Event, EventVenueFee
from apps.events.venue_fee_retry import GRACE, retry_unraised_venue_fees
from tests.events.orders_helpers import l6_space, verified

pytestmark = pytest.mark.django_db


def _event(space, *, status="published", ends_in=timedelta(days=2)):
    starts = timezone.now() + ends_in - timedelta(hours=3)
    return Event.objects.create(makerspace=space, title="Outside meetup", starts_at=starts, ends_at=starts + timedelta(hours=3),
                                registration_audience="accounts", is_public=True, status=status)


def _fee(event, payer, *, status="configured", age=GRACE + timedelta(minutes=5)):
    fee = EventVenueFee.objects.create(makerspace=event.makerspace, event=event, payer=payer, mode="custom", basis="flat",
                                       amount="50.00", status=status)
    # updated_at is auto_now, so age the row with a queryset update (which skips it).
    EventVenueFee.objects.filter(pk=fee.pk).update(updated_at=timezone.now() - age)
    return fee


@pytest.fixture
def charged(monkeypatch):
    calls = []
    monkeypatch.setattr(venue_fees, "charge", lambda event, *, actor: calls.append((event.pk, actor)))
    return calls


def test_retries_a_stale_configured_fee_of_a_published_future_event(charged):
    space = l6_space()
    fee = _fee(_event(space), verified("organiser"))
    counts = retry_unraised_venue_fees()
    assert counts == {"charged": 1, "failed": 0}
    assert charged == [(fee.event_id, None)]


@pytest.mark.parametrize("kwargs", [
    {"fee": {"age": timedelta(minutes=1)}},                      # inside the grace window: first attempt may still be running
    {"fee": {"status": "charged"}},                              # already charged
    {"fee": {"status": "free"}},                                 # nothing to charge
    {"event": {"status": "draft"}},                              # unpublished
    {"event": {"status": "cancelled"}},                          # cancelled
    {"event": {"ends_in": timedelta(hours=-1)}},                 # already over
])
def test_skips_fees_that_are_not_eligible(charged, kwargs):
    space = l6_space()
    _fee(_event(space, **kwargs.get("event", {})), verified("organiser"), **kwargs.get("fee", {}))
    assert retry_unraised_venue_fees() == {"charged": 0, "failed": 0}
    assert charged == []


def test_skips_a_space_with_the_venue_fees_switch_off(charged):
    space = l6_space(features=["events.orders"])
    _fee(_event(space), verified("organiser"))
    assert retry_unraised_venue_fees() == {"charged": 0, "failed": 0}
    assert charged == []


def test_one_failing_fee_does_not_stop_the_rest_or_leak_details(monkeypatch, caplog):
    space = l6_space()
    first, second = _fee(_event(space), verified("a")), _fee(_event(space), verified("b"))
    seen = []

    def flaky(event, *, actor):
        seen.append(event.pk)
        if event.pk == first.event_id:
            raise RuntimeError("provider down: secret-token-123")

    monkeypatch.setattr(venue_fees, "charge", flaky)
    with caplog.at_level(logging.ERROR):
        counts = retry_unraised_venue_fees()
    assert counts == {"charged": 1, "failed": 1}
    assert set(seen) == {first.event_id, second.event_id}
    record = next(r for r in caplog.records if r.message == "event_venue_fee_retry_failed")
    assert record.fee_id == first.pk and record.failure_type == "RuntimeError"
    assert "secret-token-123" not in caplog.text


def test_limit_bounds_how_many_fees_one_pass_retries(charged):
    space = l6_space()
    for name in ("a", "b", "c"):
        _fee(_event(space), verified(name))
    assert retry_unraised_venue_fees(limit=2)["charged"] == 2


def test_each_space_is_retried_independently(charged):
    one, two = l6_space("one"), l6_space("two")
    f1, f2 = _fee(_event(one), verified("a")), _fee(_event(two), verified("b"))
    assert retry_unraised_venue_fees()["charged"] == 2
    assert {pk for pk, _ in charged} == {f1.event_id, f2.event_id}


def test_the_per_minute_events_task_runs_the_retry_and_swallows_its_failure(monkeypatch, caplog):
    called = []
    monkeypatch.setattr("apps.events.venue_fee_retry.retry_unraised_venue_fees", lambda **kw: called.append(kw))
    monkeypatch.setattr("apps.events.judging.lifecycle.sweep_notices", lambda **kw: 0)
    tasks_recovery.sweep_judging_notices_task()
    assert len(called) == 1 and called[0]["limit"] >= 1

    def boom(**kw):
        raise RuntimeError("down")

    monkeypatch.setattr("apps.events.venue_fee_retry.retry_unraised_venue_fees", boom)
    with caplog.at_level(logging.ERROR):
        assert tasks_recovery.sweep_judging_notices_task() == 0
    assert "event_venue_fee_retry_pass_failed" in caplog.text

