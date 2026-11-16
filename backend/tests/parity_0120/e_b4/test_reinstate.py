"""E-B4 (D7): reinstating restores invalidated judging work (never a conflicted judge's) and the fee rules."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.events.judging import reinstate
from apps.events.submissions import entry_fees, stage_triage
from apps.events.submissions.errors import SubmissionError


def assignment(pk, snapshot=1, judge=90, state="invalidated", batch="main"):
    return SimpleNamespace(pk=pk, submission_snapshot_id=snapshot, judge_role_assignment_id=judge, state=state,
                           version=2, batch=batch, save=Mock())


def install(monkeypatch, *, rows, mode="weighted_1_5", round_state="open", eligible=True, scored=True):
    round = SimpleNamespace(pk=3, mode=mode, state=round_state)
    round.assignments = Mock()
    round.assignments.select_for_update.return_value.filter.return_value.order_by.return_value = rows
    monkeypatch.setattr(reinstate, "assert_locked", Mock())
    monkeypatch.setattr(reinstate, "runtime", lambda: SimpleNamespace(
        snapshot=lambda pk: SimpleNamespace(event_id=42), judge=lambda pk: SimpleNamespace()))
    monkeypatch.setattr(reinstate, "eligible", lambda judge, snapshot, r: eligible)
    monkeypatch.setattr(reinstate, "_was_scored", lambda r, row: scored)
    monkeypatch.setattr(reinstate, "JudgeAssignment", SimpleNamespace(objects=Mock(filter=Mock(
        return_value=Mock(values_list=Mock(return_value=[3]))))))
    monkeypatch.setattr(reinstate, "JudgingRound", SimpleNamespace(objects=Mock(select_for_update=Mock(
        return_value=Mock(filter=Mock(return_value=Mock(order_by=Mock(return_value=[round]))))))))
    notice, audit = Mock(), Mock()
    monkeypatch.setattr(reinstate, "notice", notice)
    monkeypatch.setattr(reinstate, "audit", audit)
    return notice, audit


def run():
    return reinstate.reinstate_snapshot_locked(event=SimpleNamespace(pk=42), snapshot_id=1,
                                               locks=SimpleNamespace(event_id=42), actor=object())


def test_scored_assignments_come_back_scored_and_unscored_ones_get_a_fresh_notice(monkeypatch):
    rows = [assignment(1)]
    notice, audit = install(monkeypatch, rows=rows, scored=True)
    assert run() == {"restored": 1, "skipped": 0}
    assert rows[0].state == "scored" and rows[0].version == 3 and not notice.called
    rows = [assignment(2)]
    notice, audit = install(monkeypatch, rows=rows, scored=False)
    run()
    assert rows[0].state == "assigned" and notice.call_args.args[1:] == ("judge_assigned", 2, 3)


def test_a_judge_now_in_conflict_is_not_given_the_project_back(monkeypatch):
    rows = [assignment(1)]
    install(monkeypatch, rows=rows, eligible=False)
    assert run() == {"restored": 0, "skipped": 1}
    assert rows[0].state == "invalidated"


@pytest.mark.parametrize("mode,state", [("pairwise", "open"), ("weighted_1_5", "finalized")])
def test_finalized_and_pairwise_rounds_are_left_alone(monkeypatch, mode, state):
    rows = [assignment(1)]
    install(monkeypatch, rows=rows, mode=mode, round_state=state)
    assert run() == {"restored": 0, "skipped": 1}
    assert rows[0].state == "invalidated"


def test_only_a_disqualified_entry_can_be_reinstated():
    entry = SimpleNamespace(triage="eligible", current_snapshot_id=1)
    with pytest.raises(SubmissionError) as raised:
        stage_triage.reinstate_locked(ctx=SimpleNamespace(), actor=object(), project=SimpleNamespace(state="submitted"),
                                      entry=entry, reason="appeal upheld")
    assert raised.value.status_code == 409 and raised.value.code == "not_disqualified"


def test_reinstate_flips_triage_voids_the_open_fee_case_and_restores_judging(monkeypatch):
    entry = SimpleNamespace(pk=1, triage="ineligible", version=4, current_snapshot_id=11, stage_id=2, save=Mock())
    project = SimpleNamespace(pk=8, state="submitted", triage="ineligible", triage_reason="late", version=6)
    monkeypatch.setattr(stage_triage, "furthest_entry", lambda p: entry)
    monkeypatch.setattr(entry_fees, "on_reinstated", Mock(return_value=True))
    monkeypatch.setattr(reinstate, "reinstate_snapshot_locked", Mock(return_value={"restored": 3, "skipped": 1}))
    monkeypatch.setattr("apps.events.programme_locks.current_locks", lambda pk: object())
    recorded = Mock()
    monkeypatch.setattr(stage_triage, "record", recorded)
    ctx = SimpleNamespace(event=SimpleNamespace(pk=42, makerspace=object()))
    counts = stage_triage.reinstate_locked(ctx=ctx, actor=object(), project=project, entry=entry, reason="appeal upheld")
    assert counts == {"restored": 3, "skipped": 1}
    assert entry.triage == "eligible" and entry.version == 5
    assert project.triage == "eligible" and project.version == 7
    assert recorded.call_args.args[1] == "event.submission_reinstated"
    assert recorded.call_args.kwargs["meta"]["fee_case_voided"] is True


def test_a_refunded_entry_fee_blocks_reinstatement(monkeypatch):
    from apps.payments.models import Payment
    payment = SimpleNamespace(pk=3, status=Payment.Status.PAID_ONLINE, amount=500)
    monkeypatch.setattr("apps.payments.models.Payment", SimpleNamespace(
        Status=Payment.Status, objects=SimpleNamespace(filter=lambda **kw: SimpleNamespace(first=lambda: payment))))
    monkeypatch.setattr("apps.payments.services_refund_cases._lock_payment", lambda pk: payment)
    monkeypatch.setattr("apps.payments.refund_policy.refundable_balance", lambda p: 0)
    with pytest.raises(SubmissionError) as raised:
        entry_fees.on_reinstated(event=SimpleNamespace(makerspace=object()), project=SimpleNamespace(pk=8), actor=object())
    assert raised.value.code == "fee_refunded"
