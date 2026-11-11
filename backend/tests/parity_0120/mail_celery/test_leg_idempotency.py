"""A retried or resumed fan-out job never resends a legacy email/room leg that already went out."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.integrations import fanout_jobs
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notify import EmailDelivery, LifecyclePayload, notify_lifecycle
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def _payload():
    return LifecyclePayload(text="Request issued", emails=(
        EmailDelivery(to_email="a@example.test", subject="s", text_body="b", stream="hardware", mute_event="issued"),
        EmailDelivery(to_email="b@example.test", subject="s", text_body="b", stream="hardware", mute_event="issued"),
    ))


def _run_in_job(space, job_id, capture):
    """Reproduce what fanout_jobs.run does around an adapter: a job identity and a fresh call counter."""
    tokens = fanout_jobs._job_id.set(job_id), fanout_jobs._calls.set(0)
    try:
        with capture(execute=True):
            notify_lifecycle(space, feature="hardware_requests", event="issued", build=_payload)
    finally:
        fanout_jobs._job_id.reset(tokens[0])
        fanout_jobs._calls.reset(tokens[1])


def _enabled(makerspace, feature, channel):
    return channel == "email"


def test_stable_event_key_is_identical_for_every_rerun_of_a_job():
    for job in (11, 12):
        keys = []
        for _ in range(2):  # a re-run of the job
            tokens = fanout_jobs._job_id.set(job), fanout_jobs._calls.set(0)
            keys.append((fanout_jobs.stable_event_key(), fanout_jobs.stable_event_key()))
            fanout_jobs._job_id.reset(tokens[0])
            fanout_jobs._calls.reset(tokens[1])
        assert keys[0] == keys[1] and keys[0][0] != keys[0][1]
    assert fanout_jobs.stable_event_key() != fanout_jobs.stable_event_key()  # outside a job: fresh uuid4


def test_a_resumed_job_skips_every_leg_already_handed_to_the_mail_pipeline(django_capture_on_commit_callbacks):
    space = make_space("mc-legs")
    sent = SimpleNamespace(status="pending")
    with patch("apps.integrations.notify.dispatch_email", return_value=sent) as mail, \
            patch("apps.integrations.notify.is_notification_enabled", side_effect=_enabled), \
            patch("apps.integrations.notification_legacy.sending_allowed", return_value=True):
        _run_in_job(space, 77, django_capture_on_commit_callbacks)
        assert mail.call_count == 2
        shell = NotificationEnvelope.objects.get(source_kind="legacy.lifecycle")
        assert len(shell.context["legs_done"]) == 2
        # worker killed after the sends but before the shell was marked processed: the job is re-run
        NotificationEnvelope.objects.filter(pk=shell.pk).update(processed_at=None)
        _run_in_job(space, 77, django_capture_on_commit_callbacks)
        assert mail.call_count == 2  # no leg was sent twice
    assert NotificationEnvelope.objects.filter(source_kind="legacy.lifecycle").count() == 1


def test_only_the_missing_leg_is_sent_when_the_first_run_died_between_recipients(django_capture_on_commit_callbacks):
    space = make_space("mc-half")
    calls = []

    def flaky(**kwargs):
        calls.append(kwargs["to_email"])
        if len(calls) == 2:
            raise RuntimeError("provider timeout")
        return SimpleNamespace(status="pending")
    with patch("apps.integrations.notify.dispatch_email", side_effect=flaky), \
            patch("apps.integrations.notify.is_notification_enabled", side_effect=_enabled), \
            patch("apps.integrations.notification_legacy.sending_allowed", return_value=True):
        _run_in_job(space, 78, django_capture_on_commit_callbacks)   # recipient a ok, recipient b failed
        NotificationEnvelope.objects.update(processed_at=None)
        _run_in_job(space, 78, django_capture_on_commit_callbacks)   # re-run: a skipped, b sent
    assert calls == ["a@example.test", "b@example.test", "b@example.test"]


def test_inline_calls_outside_a_job_are_unchanged(django_capture_on_commit_callbacks):
    space = make_space("mc-inline-legs")
    with patch("apps.integrations.notify.dispatch_email", return_value=SimpleNamespace(status="pending")) as mail, \
            patch("apps.integrations.notify.is_notification_enabled", side_effect=_enabled), \
            patch("apps.integrations.notification_legacy.sending_allowed", return_value=True):
        for _ in range(2):
            with django_capture_on_commit_callbacks(execute=True):
                notify_lifecycle(space, feature="hardware_requests", event="issued", build=_payload)
    assert mail.call_count == 4  # two independent events, two recipients each
