"""L21b money and switches: prize payouts (C-38), entry fee (X50), leader-pays team (C-39), C-37 emails.

No money ever moves: payouts are recorded expenses, refunds are only due cases staff decide.
"""
from dataclasses import replace
from decimal import Decimal

import pytest
from django.http import Http404

from apps.events.judging import options, payouts
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_payouts import HackathonPrizePayout
from apps.events.programme_charges import close_charge, find_charge, raise_charge, settled_or_free
from apps.events.submissions.entry_fees import on_disqualified, require_submit_paid
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_projects import HackathonSubmission
from apps.payments.models import Payment, RefundCase
from apps.payments.models_ledger_entries import LedgerEntry
from tests.events.pairwise_helpers import command, pairwise_world

pytestmark = pytest.mark.django_db


def enable(world, *keys):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | set(keys))
    world.space.save(update_fields=["enabled_features"])


@pytest.fixture
def world(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=2, judges=3, enabled=False)
    enable(world, "charges.enabled", "charges.events")
    return world


def published_award(world, amount=Decimal("250.00")):
    """A prize, a finalized weighted round and an announced result naming the first project."""
    from apps.events.judging.definitions_workflow import save_definition
    from apps.events.judging.models_results import EventAward
    from apps.events.judging.results_workflow import finalize, publish
    from tests.l21b_local.test_finalists_and_rounds import assign_all, close_and_finalize, score_all, weighted_round
    prize = save_definition(world.event.pk, actor=world.manager, kind="prizes",
                            data=command(name="Best build", amount_per_winner=str(amount)))
    for pk in world.snapshots:
        world.ports.snaps[pk] = replace(world.ports.snaps[pk], prize_ids=(prize["id"],))
    round = weighted_round(world, "heats")
    assign_all(world, round)
    score_all(world, round, dict(zip(world.snapshots, (5, 2))))
    close_and_finalize(world, round)
    result = finalize(world.event.pk, actor=world.manager, data=command(0, round_ids=[round.pk], integrity_reviewed=True,
                      awards=[{"prize_id": prize["id"], "snapshot_id": world.snapshots[0], "rank": 1}]))
    publish(world.event.pk, actor=world.manager, data=command(result["version"], result_revision_id=result["id"]))
    return EventAward.objects.get(result_id=result["id"])


def test_payout_is_a_ledger_expense_and_a_reversal_voids_it(world):
    enable(world, "events.prize_payouts")
    award = published_award(world)
    row = payouts.record_payout(world.event.pk, actor=world.manager, data=command(
        0, award_id=award.pk, method="bank_transfer", reference="TX-1", paid_on="2026-11-05"))
    entry = LedgerEntry.objects.get(pk=row["ledger_entry_id"])
    assert (entry.kind, entry.domain, entry.category, entry.amount) == ("expense", "events", "prize", Decimal("250.00"))
    assert row["recipient_id"] == world.ports.snaps[world.snapshots[0]].member_ids[0]  # defaults to the leader
    with pytest.raises(ProgrammeError) as twice:
        payouts.record_payout(world.event.pk, actor=world.manager, data=command(
            0, award_id=award.pk, method="cash", paid_on="2026-11-05"))
    assert twice.value.detail["code"] == "payout_exists"
    reversal = payouts.reverse_payout(world.event.pk, row["id"], actor=world.manager, data=command(0, reason="Wrong account"))
    entry.refresh_from_db()
    assert reversal["kind"] == "reversal" and entry.voided_at is not None
    again = payouts.record_payout(world.event.pk, actor=world.manager, data=command(
        0, award_id=award.pk, method="cash", paid_on="2026-11-06", amount="200.00"))
    assert LedgerEntry.objects.get(pk=again["ledger_entry_id"]).voided_at is None


def test_payout_rows_are_append_only(world):
    enable(world, "events.prize_payouts")
    award = published_award(world)
    row = payouts.record_payout(world.event.pk, actor=world.manager, data=command(
        0, award_id=award.pk, method="cash", paid_on="2026-11-05"))
    payout = HackathonPrizePayout.objects.get(pk=row["id"])
    payout.reference = "edited"
    with pytest.raises(RuntimeError):
        payout.save()
    with pytest.raises(RuntimeError):
        HackathonPrizePayout.objects.filter(pk=payout.pk).update(reference="edited")


def test_only_record_payment_holders_or_the_event_manager_record_payouts(world):
    enable(world, "events.prize_payouts")
    award = published_award(world)
    judge = world.judges[0]  # an event role, no space finance or events action
    with pytest.raises(Http404):
        payouts.record_payout(world.event.pk, actor=judge, data=command(0, award_id=award.pk, method="cash", paid_on="2026-11-05"))
    assert payouts.may_record(world.manager, world.space.pk)


def test_payouts_need_published_results_and_the_switch(world):
    with pytest.raises(Http404):
        payouts.listing(world.event.pk, actor=world.manager)
    enable(world, "events.prize_payouts")
    rows, awards = payouts.listing(world.event.pk, actor=world.manager)
    assert rows == [] and awards == []


def test_new_events_start_with_both_hackathon_emails_off(world):
    assert options.option(world.event, "results_email") is False
    assert options.option(world.event, "submission_receipt_email") is False
    assert options.projection(world.event)["version"] == 0


def test_migration_keeps_existing_events_emails_on(world):
    from importlib import import_module
    from django.apps import apps
    from apps.events.judging.models_options import HackathonProgrammeOptions
    import_module("apps.events.migrations.0068_l21b_guards_and_options").keep_existing_emails(apps, None)
    row = HackathonProgrammeOptions.objects.get(event=world.event)
    assert row.results_email and row.submission_receipt_email and not row.finalists_email


def test_results_email_follows_the_switch_and_send_now_works_once(world):
    from apps.events.judging.models_results import JudgingNotice
    published_award(world)
    assert not JudgingNotice.objects.filter(kind="results_published").exists()
    current = options.projection(world.event)
    sent = options.send_results_email(world.event.pk, actor=world.manager, data=command(current["published_result_version"]))
    assert sent["results_email_sent"] is True
    with pytest.raises(ProgrammeError) as again:
        options.send_results_email(world.event.pk, actor=world.manager, data=command(current["published_result_version"]))
    assert again.value.detail["code"] == "already_sent"


def test_submission_receipt_is_not_sent_with_the_switch_off(world, monkeypatch):
    from apps.events.submissions import notifications
    sent = []
    monkeypatch.setattr(notifications, "emit", lambda **kwargs: sent.append(kwargs))
    project = HackathonSubmission.objects.filter(event=world.event).first()
    notifications.enqueue_locked(project=project, action="submit")
    assert sent == []
    options.update(world.event.pk, actor=world.manager, data=command(0, submission_receipt_email=True))
    notifications.enqueue_locked(project=project, action="submit")
    assert sent


def _project(world):
    return HackathonSubmission.objects.filter(event=world.event).select_related("team").first()


def test_entry_fee_holds_the_draft_until_paid(world):
    enable(world, "events.hackathons", "events.entry_fees")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00"))
    project = _project(world)
    with pytest.raises(SubmissionError) as held:
        require_submit_paid(project, world.event, project.team)
    assert held.value.code == "entry_fee_required"
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk, member=project.team.leader,
                           amount="500.00", actor=project.team.leader, audit_action="event.submission.fee_raised", target={})
    with pytest.raises(SubmissionError):
        require_submit_paid(project, world.event, project.team)
    Payment.objects.filter(pk=payment.pk).update(status="paid_offline")
    require_submit_paid(project, world.event, project.team)


def test_entry_fee_switched_off_or_untracked_charges_and_holds_nothing(world):
    options.update(world.event.pk, actor=world.manager, data=command(0))
    project = _project(world)
    require_submit_paid(project, world.event, project.team)  # no capability: nothing held
    enable(world, "events.entry_fees")
    world.space.enabled_features = [key for key in world.space.enabled_features if key != "charges.events"]
    world.space.save(update_fields=["enabled_features"])
    require_submit_paid(project, world.event, project.team)


@pytest.mark.parametrize("refund_switch, expect_case", [(True, True), (False, False)])
def test_disqualification_opens_a_due_case_only_with_the_refund_switch(world, refund_switch, expect_case):
    enable(world, "events.entry_fees")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00",
                                                                    refund_on_disqualification=refund_switch))
    project = _project(world)
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk, member=project.team.leader,
                           amount="500.00", actor=project.team.leader, audit_action="event.submission.fee_raised", target={})
    Payment.objects.filter(pk=payment.pk).update(status="paid_offline")
    on_disqualified(event=world.event, project=project, actor=world.manager)
    cases = RefundCase.objects.filter(payment=payment)
    assert cases.exists() is expect_case
    if expect_case:
        assert cases.get().kind == "due" and cases.get().reason_code == "submission_disqualified"
    assert Payment.objects.get(pk=payment.pk).status == "paid_offline"  # never refunded automatically


def test_disqualification_voids_a_pending_fee(world):
    enable(world, "events.entry_fees")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00"))
    project = _project(world)
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk, member=project.team.leader,
                           amount="500.00", actor=project.team.leader, audit_action="event.submission.fee_raised", target={})
    on_disqualified(event=world.event, project=project, actor=world.manager)
    assert Payment.objects.get(pk=payment.pk).status == "canceled"  # Payment.Status.CANCELED


def test_leader_pays_once_and_size_changes_never_reprice(world, django_capture_on_commit_callbacks):
    from apps.events.hackathons.team_payments import raise_team_charge, team_payment_settled
    enable(world, "events.paid_teams")
    options.update(world.event.pk, actor=world.manager, data=command(0, team_fee="1500.00"))
    team = _project(world).team
    with django_capture_on_commit_callbacks(execute=True):
        team.state = "locked"
        team.save()
    payment = find_charge(world.event, "team_registration", team.pk)
    assert payment.member_id == team.leader_id and payment.amount == Decimal("1500.00")
    assert not team_payment_settled(team)
    options.update(world.event.pk, actor=world.manager, data=command(1, team_fee="9999.00"))
    assert raise_team_charge(team).pk == payment.pk and Payment.objects.get(pk=payment.pk).amount == Decimal("1500.00")
    assert Payment.objects.filter(subject_type="team_registration").count() == 1  # no per-member charges


def test_a_disbanded_paid_team_opens_a_due_case_for_the_leader(world, django_capture_on_commit_callbacks):
    enable(world, "events.paid_teams")
    options.update(world.event.pk, actor=world.manager, data=command(0, team_fee="1500.00"))
    team = _project(world).team
    payment = raise_charge(event=world.event, subject_type="team_registration", subject_id=team.pk, member=team.leader,
                           amount="1500.00", actor=team.leader, audit_action="event.team.payment_raised", target={})
    Payment.objects.filter(pk=payment.pk).update(status="paid_online")
    with django_capture_on_commit_callbacks(execute=True):
        team.state = "disbanded"
        team.save()
    case = RefundCase.objects.get(payment=payment)
    assert (case.kind, case.reason_code, case.due_amount) == ("due", "team_rejected", Decimal("1500.00"))
    assert settled_or_free(world.event, "team_registration", team.pk)


def test_close_charge_with_nothing_raised_is_a_no_op(world):
    team = _project(world).team
    assert close_charge(event=world.event, subject_type="team_registration", subject_id=team.pk, actor=world.manager,
                        reason_code="team_rejected", audit_action="event.team.payment_closed") is None
