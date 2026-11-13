"""E-B4 (D8): unpublish clears the public pointer; republishing never emails anyone twice."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from apps.events.judging import results_unpublish as unpublish_module
from apps.events.judging.errors import ProgrammeError


def install(monkeypatch, *, state, paid=False):
    event = SimpleNamespace(pk=42)

    @contextmanager
    def mutation(*args, **kwargs):
        yield event, object()
    states = Mock()
    states.objects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = state
    monkeypatch.setattr(unpublish_module, "mutation", mutation)
    monkeypatch.setattr(unpublish_module, "command", lambda *a, run, **k: run())
    monkeypatch.setattr(unpublish_module, "ResultPublicationState", states)
    for name in ("HackathonPrizePayout", "HackathonPrizeShare"):
        model = Mock()
        model.objects.filter.return_value.exists.return_value = paid
        monkeypatch.setattr(unpublish_module, name, model)
    audit = Mock()
    monkeypatch.setattr(unpublish_module, "audit", audit)
    return audit


def published_state():
    result = SimpleNamespace(pk=101, version=2, awards=Mock())
    result.awards.values_list.return_value = [1, 2]
    return SimpleNamespace(version=4, current_announcement_id=9, current_announcement=SimpleNamespace(result=result),
                           save=Mock())


def body(version=2):
    return {"operation_id": str(uuid4()), "expected_version": version}


def test_unpublish_clears_only_the_pointer_and_audits(monkeypatch):
    state = published_state()
    audit = install(monkeypatch, state=state)
    response = unpublish_module.unpublish(42, actor=SimpleNamespace(pk=1), data=body())
    assert state.current_announcement is None and state.version == 5
    assert response["state"] == "finalized" and "publish" in response["allowed_actions"]
    assert audit.call_args.args[2] == "results_unpublished"


@pytest.mark.parametrize("case,code", [("none", "not_published"), ("stale", "stale_version"), ("paid", "results_in_use")])
def test_unpublish_refusals_are_typed_409s(monkeypatch, case, code):
    state = None if case == "none" else published_state()
    install(monkeypatch, state=state, paid=case == "paid")
    with pytest.raises(ProgrammeError) as raised:
        unpublish_module.unpublish(42, actor=SimpleNamespace(pk=1), data=body(9 if case == "stale" else 2))
    assert raised.value.status_code == 409 and raised.value.detail["code"] == code


def run_deliver(monkeypatch, envelopes):
    """Run deliver_cancelled for one recipient whose earlier envelopes are `envelopes`."""
    row = SimpleNamespace(pk=5, revision=2, kind="results_published", event_id=42,
                          event=SimpleNamespace(makerspace=object()))
    monkeypatch.setattr(unpublish_module, "JudgingNotice", SimpleNamespace(objects=Mock(select_related=Mock(
        return_value=Mock(get=Mock(return_value=row))))))
    monkeypatch.setattr(unpublish_module, "recipients", lambda r: (7,))
    users = Mock()
    users.objects.filter.return_value.order_by.return_value = [SimpleNamespace(pk=7)]
    monkeypatch.setattr(unpublish_module, "User", users)
    monkeypatch.setattr(unpublish_module, "person_q", lambda: None)
    monkeypatch.setattr(unpublish_module, "NotificationEnvelope", Mock(objects=Mock(
        filter=Mock(return_value=envelopes))))
    emit = Mock()
    monkeypatch.setattr(unpublish_module, "emit", emit)
    unpublish_module.deliver_cancelled(5, epoch=6)
    return emit


def envelope(states, processed=True):
    return SimpleNamespace(processed_at=object() if processed else None,
                           deliveries=Mock(values_list=Mock(return_value=states)))


def test_republish_never_emails_someone_who_already_received_the_message(monkeypatch):
    assert not run_deliver(monkeypatch, [envelope(["delivered"])]).called
    assert not run_deliver(monkeypatch, [envelope(["sent"]), envelope(["skipped"])]).called


def test_republish_never_double_queues_a_message_still_in_flight(monkeypatch):
    assert not run_deliver(monkeypatch, [envelope([], processed=False)]).called


def test_republish_emails_only_those_whose_message_was_cancelled(monkeypatch):
    emit = run_deliver(monkeypatch, [envelope(["skipped"])])
    assert emit.call_args.kwargs["dedup_key"] == "event-judging:5:2:7:p6"
    emit = run_deliver(monkeypatch, [])
    assert emit.call_args.kwargs["dedup_key"] == "event-judging:5:2:7"
