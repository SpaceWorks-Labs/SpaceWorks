"""Hack-money G1, G2 and G15: cancelled events, withdrawals and shortlists close hackathon charges;
staff can raise a team charge a failed signal never raised. Money never moves: pending charges are
voided and paid ones open DUE refund cases for staff to decide (#59)."""
from decimal import Decimal

import pytest
from django.http import Http404

from apps.events.judging import options
from apps.events.programme_charges import close_charge, close_for_cancelled_event, find_charge
from apps.events.submissions.entry_fees import on_shortlist_published, on_withdrawn
from apps.payments.models import Payment, RefundCase
from tests.hackmoney_local.helpers import command, enable, paid_fee, projects, team_charge, world  # noqa: F401

pytestmark = pytest.mark.django_db
VOID = ("canceled", "cancelled")


def fees_on(world, **switches):
    enable(world, "events.entry_fees", "events.paid_teams")
    options.update(world.event.pk, actor=world.manager, data=command(0, entry_fee="500.00", team_fee="1500.00", **switches))


# G1 -------------------------------------------------------------------------------------------

def test_cancelling_the_event_voids_pending_and_opens_due_cases_on_paid_charges(world, django_capture_on_commit_callbacks):
    from apps.events import services
    fees_on(world)
    first, second = projects(world)
    paid = paid_fee(world, first)
    pending = paid_fee(world, second, status="pending")
    team = team_charge(world, first.team)
    with django_capture_on_commit_callbacks(execute=True):
        services.cancel(world.event, actor=world.manager)
    assert Payment.objects.get(pk=pending.pk).status in VOID
    for payment in (paid, team):
        case = RefundCase.objects.get(payment=payment)
        assert (case.kind, case.reason_code, case.due_amount) == ("due", "event_cancelled", payment.amount)
        assert Payment.objects.get(pk=payment.pk).status in ("paid_offline", "paid_online")  # never refunded here


def test_cancel_closure_is_idempotent_with_an_earlier_case(world, django_capture_on_commit_callbacks):
    fees_on(world, refund_on_disqualification=True)
    project = projects(world)[0]
    payment = paid_fee(world, project)
    close_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk, actor=world.manager,
                 reason_code="submission_disqualified", audit_action="event.submission.fee_closed")
    with django_capture_on_commit_callbacks(execute=True):
        close_for_cancelled_event(world.event, world.manager)
    case = RefundCase.objects.get(payment=payment)  # still exactly one case, not grown
    assert case.reason_code == "submission_disqualified" and case.due_amount == Decimal("500.00")


@pytest.mark.parametrize("team_mode", ["solo", "individual_then_team", "team_together"])
def test_cancel_reaches_team_charges_in_every_team_mode(world, team_mode, django_capture_on_commit_callbacks):
    from apps.events.hackathons.admission_models import HackathonConfig
    fees_on(world)
    HackathonConfig.objects.filter(event=world.event).update(team_mode=team_mode)
    team = projects(world)[0].team
    payment = team_charge(world, team)
    world.event.status = "cancelled"
    world.event.save(update_fields=["status"])
    with django_capture_on_commit_callbacks(execute=True):
        close_for_cancelled_event(world.event, world.manager)
    assert RefundCase.objects.get(payment=payment).reason_code == "event_cancelled"


def test_a_cohort_closed_by_cancellation_is_owed_for_the_cancellation(world):
    from apps.events.hackathons.team_payments import close_team_charge
    fees_on(world)
    team = projects(world)[0].team
    payment = team_charge(world, team)
    team.event.status = "cancelled"
    close_team_charge(team)
    assert RefundCase.objects.get(payment=payment).reason_code == "event_cancelled"


# G2 -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("switch, expect_case", [(True, True), (False, False)])
def test_withdrawal_opens_a_due_case_only_with_the_switch(world, switch, expect_case):
    fees_on(world, refund_on_withdrawal=switch)
    project = projects(world)[0]
    payment = paid_fee(world, project)
    on_withdrawn(event=world.event, project=project, actor=project.team.leader)
    cases = RefundCase.objects.filter(payment=payment)
    assert cases.exists() is expect_case
    if expect_case:
        assert cases.get().reason_code == "submission_withdrawn"


def test_withdrawal_always_voids_a_pending_fee(world):
    fees_on(world)
    project = projects(world)[0]
    payment = paid_fee(world, project, status="pending")
    on_withdrawn(event=world.event, project=project, actor=project.team.leader)
    assert Payment.objects.get(pk=payment.pk).status in VOID


def publish_finalists(world, snapshot_ids):
    from django.utils import timezone
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.models_finalists import FinalistAdvance, FinalistAnnouncement, JudgingFinalist
    from apps.events.models import HackathonSubmission, SubmissionSnapshot
    # The fixture seals snapshots but never points the submission at one; the seam reads `current_snapshot`.
    for snap in SubmissionSnapshot.objects.filter(pk__in=world.snapshots):
        HackathonSubmission.objects.filter(pk=snap.submission_id).update(current_snapshot_id=snap.pk)
    source = JudgingRound.objects.create(event=world.event, key="heats", mode="weighted_1_5")
    target = JudgingRound.objects.create(event=world.event, key="final", mode="weighted_1_5")
    advance = FinalistAdvance.objects.create(event=world.event, source_round=source, target_round=target,
                                             selection="manual", fingerprint="0" * 64, created_by=world.manager)
    for rank, pk in enumerate(snapshot_ids, 1):
        JudgingFinalist.objects.create(advance=advance, snapshot_id=pk, source_rank=rank)
    return FinalistAnnouncement.objects.create(event=world.event, advance=advance, published_at=timezone.now(),
                                               published_by=world.manager)


@pytest.mark.parametrize("switch", [True, False])
def test_not_shortlisted_paid_fees_open_due_cases_only_with_the_switch(world, switch):
    fees_on(world, refund_if_not_shortlisted=switch)
    advanced, dropped = projects(world)
    kept, owed = paid_fee(world, advanced), paid_fee(world, dropped)
    publish_finalists(world, [world.snapshots[0]])
    on_shortlist_published(event=world.event, actor=world.manager)
    assert not RefundCase.objects.filter(payment=kept).exists()
    assert RefundCase.objects.filter(payment=owed, reason_code="not_shortlisted").exists() is switch


def test_the_shortlist_seam_reads_published_finalists(world):
    from apps.events.judging.shortlist_seam import not_shortlisted_project_ids, was_shortlisted
    advanced, dropped = projects(world)
    assert not_shortlisted_project_ids(world.event) == []  # nothing published yet
    publish_finalists(world, [world.snapshots[0]])
    assert was_shortlisted(world.event, advanced.pk) and not was_shortlisted(world.event, dropped.pk)
    assert not_shortlisted_project_ids(world.event) == [dropped.pk]


def test_the_refund_switches_are_off_for_new_events(world):
    assert options.option(world.event, "refund_on_withdrawal") is False
    assert options.option(world.event, "refund_if_not_shortlisted") is False
    assert options.projection(world.event)["refund_on_withdrawal"] is False


# G15 ------------------------------------------------------------------------------------------

def test_staff_see_and_raise_a_missing_team_charge(world):
    from apps.events.judging import team_charges
    fees_on(world)
    team = projects(world)[0].team
    type(team).objects.filter(pk=team.pk).update(state="locked")  # no signal ran: the charge "failed"
    rows = team_charges.missing(world.event.pk, actor=world.manager)
    assert [row["team_id"] for row in rows] == [team.pk] and rows[0]["amount"] == Decimal("1500.00")
    raised = team_charges.raise_now(world.event.pk, team.pk, actor=world.manager, data=command(0))
    payment = find_charge(world.event, "team_registration", team.pk)
    assert raised["payment_id"] == payment.pk and payment.member_id == team.leader_id and payment.status == "pending"
    again = team_charges.raise_now(world.event.pk, team.pk, actor=world.manager, data=command(0))
    assert again["payment_id"] == payment.pk
    assert team_charges.missing(world.event.pk, actor=world.manager) == []


def test_raise_refuses_a_team_that_owes_nothing_or_another_events_team(world):
    from apps.events.judging import team_charges
    fees_on(world)
    team = projects(world)[0].team  # still forming: owes nothing
    with pytest.raises(Http404):
        team_charges.raise_now(world.event.pk, team.pk, actor=world.manager, data=command(0))
    with pytest.raises(Http404):
        team_charges.raise_now(world.event.pk, 999999, actor=world.manager, data=command(0))


def test_team_charge_retry_needs_the_paid_teams_switch(world):
    from apps.events.judging import team_charges
    with pytest.raises(Http404):
        team_charges.missing(world.event.pk, actor=world.manager)
