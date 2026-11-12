"""NCA audit 0.12.0 (decision 332a): a cut-out attempt that hits its time limit is retried with backoff and stays
bounded by MAX_ATTEMPTS, including when the worker was hard-killed and the row was left running."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.card_designs import cutouts
from apps.card_designs.models import CardPhotoCutout

from .test_cutouts import _answer, _setup

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)


def test_a_soft_time_limit_requeues_with_backoff_then_fails_typed(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-soft-limit")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    CardPhotoCutout.objects.filter(pk=row.pk).update(state="running", attempts=1)
    assert cutouts.timed_out(row.pk) == cutouts.BACKOFF_SECONDS[0]
    row.refresh_from_db()
    assert row.state == "queued" and row.error_code == "provider_timeout"
    CardPhotoCutout.objects.filter(pk=row.pk).update(state="running", attempts=cutouts.MAX_ATTEMPTS)
    assert cutouts.timed_out(row.pk) is None
    row.refresh_from_db()
    assert row.state == "failed" and row.error_code == "provider_timeout"


def test_an_abandoned_row_past_its_attempts_is_failed_not_reclaimed_forever(monkeypatch, store, original_photo):
    _space, sm, _user, card = _setup("co-abandoned")
    _answer(monkeypatch)
    row = cutouts.request(sm, "member_card", card)
    stale = timezone.now() - timedelta(seconds=cutouts.STALE_AFTER_SECONDS + 60)
    CardPhotoCutout.objects.filter(pk=row.pk).update(state="running", attempts=cutouts.MAX_ATTEMPTS, updated_at=stale)
    assert cutouts.run(row.pk) is None
    row.refresh_from_db()
    assert row.state == "failed" and row.error_code == "provider_timeout" and row.attempts == cutouts.MAX_ATTEMPTS
