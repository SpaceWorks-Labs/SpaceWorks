"""Deferred fan-out: a request enqueues one id-only job; the worker runs it idempotently, in order, with backoff."""
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations import fanout_jobs
from apps.integrations.fanout_jobs import LEGACY_KIND, MAX_ATTEMPTS, deferred_fanout, run
from apps.integrations.models_contract import NotificationEnvelope
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
CALLS = []


@deferred_fanout(feature="events")
def probe_adapter(space, label="x"):
    CALLS.append((space.pk, label))
    if label == "boom":
        raise RuntimeError("provider down")


@pytest.fixture(autouse=True)
def _reset(settings):
    CALLS.clear()
    settings.CELERY_TASK_ALWAYS_EAGER = False
    yield


def _queue(space, django_capture_on_commit_callbacks, **kwargs):
    with patch("apps.integrations.notification_outbox.enqueue") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            probe_adapter(space, **kwargs)
    return enqueue


def test_request_only_writes_an_id_job_and_enqueues_after_commit(django_capture_on_commit_callbacks):
    space = make_space("mc-defer")
    enqueue = _queue(space, django_capture_on_commit_callbacks)
    assert CALLS == []  # nothing resolved, rendered or sent in the request
    shell = NotificationEnvelope.objects.get(source_kind=LEGACY_KIND)
    first = shell.context["fanout"]["args"][0]
    assert (first["m"], first["pk"]) == ("makerspaces.makerspace", space.pk)
    enqueue.assert_called_once_with(shell.pk)


def test_worker_runs_the_job_once_and_a_replay_is_a_no_op(django_capture_on_commit_callbacks):
    space = make_space("mc-once")
    _queue(space, django_capture_on_commit_callbacks)
    shell = NotificationEnvelope.objects.get(source_kind=LEGACY_KIND)
    assert run(shell) is True
    assert run(shell) is False and CALLS == [(space.pk, "x")]
    shell.refresh_from_db()
    assert shell.processed_at is not None and shell.context["fanout"]["state"] == "done"


def test_failure_is_recorded_retried_with_backoff_then_marked_dead(django_capture_on_commit_callbacks):
    space = make_space("mc-fail")
    _queue(space, django_capture_on_commit_callbacks, label="boom")
    shell = NotificationEnvelope.objects.get(source_kind=LEGACY_KIND)
    assert run(shell) is False
    shell.refresh_from_db()
    assert shell.processed_at is None and shell.available_at > timezone.now()
    assert shell.context["fanout"]["state"] == "failed" and shell.context["fanout"]["error"] == "RuntimeError"
    for _ in range(MAX_ATTEMPTS):
        shell.refresh_from_db()
        run(shell)
    shell.refresh_from_db()
    assert shell.context["fanout"]["state"] == "dead" and shell.processed_at is not None


def test_jobs_for_one_subject_run_in_order(django_capture_on_commit_callbacks):
    from django.contrib.contenttypes.models import ContentType
    from apps.makerspaces.models import Makerspace
    space = make_space("mc-order")
    _queue(space, django_capture_on_commit_callbacks, label="first")
    _queue(space, django_capture_on_commit_callbacks, label="second")
    first, second = NotificationEnvelope.objects.filter(source_kind=LEGACY_KIND).order_by("pk")
    NotificationEnvelope.objects.filter(pk__in=[first.pk, second.pk]).update(
        subject_id=str(space.pk), subject_type=ContentType.objects.get_for_model(Makerspace))
    assert run(NotificationEnvelope.objects.get(pk=second.pk)) is False and CALLS == []
    assert run(NotificationEnvelope.objects.get(pk=first.pk)) is True
    assert run(NotificationEnvelope.objects.get(pk=second.pk)) is True
    assert [label for _, label in CALLS] == ["first", "second"]


def test_eager_celery_runs_inline(settings):
    space = make_space("mc-inline")
    settings.CELERY_TASK_ALWAYS_EAGER = True
    probe_adapter(space, label="eager")
    assert CALLS == [(space.pk, "eager")]
    assert not NotificationEnvelope.objects.filter(source_kind=LEGACY_KIND).exists()


def test_unserialisable_arguments_fall_back_to_inline_instead_of_losing_the_notice():
    space = make_space("mc-lambda")
    probe_adapter(space, label=lambda: 1)  # the real encoder refuses a lambda, so the call runs inline
    assert not NotificationEnvelope.objects.filter(source_kind=LEGACY_KIND).exists()
    assert len(CALLS) == 1


def test_a_deleted_subject_drops_the_job_instead_of_retrying_forever(django_capture_on_commit_callbacks):
    space = make_space("mc-gone")
    _queue(space, django_capture_on_commit_callbacks)
    shell = NotificationEnvelope.objects.get(source_kind=LEGACY_KIND)
    shell.context["fanout"]["args"][0]["pk"] = 0
    shell.save(update_fields=["context"])
    assert run(shell) is False and CALLS == []
    shell.refresh_from_db()
    assert shell.context["fanout"]["state"] == "subject_gone" and shell.processed_at is not None


SEEN = []


@deferred_fanout(feature="events")
def read_state(row):
    SEEN.append(row.geofence_radius_m)


def test_call_time_state_is_overlaid_so_dedup_keys_do_not_drift(django_capture_on_commit_callbacks):
    """The worker sees the row as the caller did (counters, status, timestamps), not as it is when the job runs."""
    from apps.makerspaces.models import Makerspace
    SEEN.clear()
    space = make_space("mc-snapshot")
    space.geofence_radius_m = 40
    with patch("apps.integrations.notification_outbox.enqueue"):
        with django_capture_on_commit_callbacks(execute=True):
            read_state(space)
    Makerspace.objects.filter(pk=space.pk).update(geofence_radius_m=99)  # state moves on before the worker runs
    shell = NotificationEnvelope.objects.get(source_kind=LEGACY_KIND, context__fanout__fn__endswith="read_state")
    assert run(shell) is True and SEEN == [40]


def test_nothing_personal_enters_the_job_row():
    from apps.integrations.fanout_codec import Unserializable, _encode
    with pytest.raises(Unserializable):
        _encode("someone@example.test")
    with pytest.raises(Unserializable):
        _encode({"someone@example.test": 1})
    from apps.accounts.models import User
    user = User.objects.create_user(username="mc-pii", email="pii@example.test")
    assert _encode(user)["f"] == {}  # accounts rows carry the id only, no snapshot


def test_codec_round_trips_dates_decimals_and_ids():
    from datetime import date, datetime, timezone as tz
    from decimal import Decimal
    from apps.integrations.fanout_codec import _decode, _encode
    value = {"when": datetime(2026, 1, 2, 3, 4, tzinfo=tz.utc), "day": date(2026, 1, 2), "amount": Decimal("1.50"),
             "ids": [1, 2, 3]}
    assert _decode(_encode(value)) == value
