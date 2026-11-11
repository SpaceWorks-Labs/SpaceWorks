"""Full-manager result finalization, append-only correction and announcement."""

from django.utils.translation import gettext
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .boundary import audit, command, digest, mutation, notice
from .calculations import ALGORITHM_VERSION
from .errors import ProgrammeError, invalid, require_version
from .models_definitions import HackathonPrize, JudgingRound
from .models_results import EventAward, EventResultRevision, EventResultRound, ResultAnnouncement, ResultPublicationState, SponsorWinnerProposal
from .models_scoring import JudgingReason
from .ports import runtime
from .projections import round_calculation
from .serializers import PublishResultInput, ResultsInput, validated


def preview(event_id, *, actor, round_ids):
    from apps.events import event_authority
    event = event_authority.get_event(actor, event_id, None)
    runtime().require_programme(event)
    rounds = list(JudgingRound.objects.filter(event_id=event_id, pk__in=round_ids).order_by("pk"))
    if len(rounds) != len(set(round_ids)):
        raise Http404
    return {"event_id": event_id, "algorithm_version": ALGORITHM_VERSION,
            "rounds": [{"id": r.pk, **round_calculation(r)} for r in rounds]}


def finalize(event_id, *, actor, data, correction=False):
    values = validated(ResultsInput, data)
    with mutation(event_id, actor, permission=None) as (event, _):
        def run():
            previous = EventResultRevision.objects.filter(event=event).order_by("-version").first()
            version = previous.version if previous else 0
            if values["expected_version"] != version:
                raise ProgrammeError("stale_version", "This item changed.", current_version=version)
            if previous and not correction:
                invalid("Create a correction to preserve finalized history.")
            if correction and (not previous or not values.get("reason")):
                raise ValidationError({"reason": gettext("A correction requires the previous result and a reason.")})
            if not values["integrity_reviewed"]:
                raise ValidationError({"integrity_reviewed": gettext("Review integrity flags before finalization.")})
            rounds = list(JudgingRound.objects.select_for_update().filter(
                event=event, pk__in=values["round_ids"]).order_by("pk"))
            if len(rounds) != len(values["round_ids"]):
                raise Http404
            from .models_finalists import FinalistAdvance
            if FinalistAdvance.objects.filter(event=event, source_round__in=rounds).exists():
                invalid("Results come from the final round; a selected round advanced finalists.")
            calculations = []
            for round in rounds:
                if round.state != "finalized":
                    invalid("Finalize every selected judging round first.")
                calculation = round_calculation(round)
                if not calculation["coverage_complete"] and not round.coverage_exception_id:
                    raise ProgrammeError("incomplete_coverage", "Record an explicit coverage exception before finalization.")
                calculations.append(calculation)
            awards = _awards(event, values["awards"], calculations, rounds)
            aggregate = {"rounds": [{"round_id": r.pk, **c} for r, c in zip(rounds, calculations)],
                         "awards": [{key: value for key, value in a.items() if key != "tie_reason"} for a in awards]}
            reason = _reason(event, actor, values.get("reason"))
            result = EventResultRevision.objects.create(event=event, version=version + 1,
                algorithm_version=ALGORITHM_VERSION, aggregates=aggregate, content_sha256=digest(aggregate),
                created_by=actor, finalized_at=timezone.now(), correction_of=previous, reason=reason)
            for round, calculation in zip(rounds, calculations):
                EventResultRound.objects.create(result=result, round=round, configuration=round.configuration,
                                                calculation=calculation)
            for award in awards:
                EventAward.objects.create(result=result, prize_id=award["prize_id"],
                    prize_name=award["prize_name"],
                    submission_snapshot_id=award["snapshot_id"], rank=award["rank"],
                    public_requested=award["public_requested"], reason=_reason(event, actor, award.get("tie_reason")))
            audit(event, actor, "results_corrected" if correction else "results_finalized", result,
                  version=result.version, count=len(awards))
            return {"id": result.pk, "event_id": event_id, "version": result.version,
                    "state": "finalized", "allowed_actions": ["publish"], "content_sha256": result.content_sha256}
        return command(event, actor, values, path="results/correct" if correction else "results/finalize", run=run)


def _reason(event, actor, text):
    return JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id,
                                        actor=actor, body=text) if text else None


def _awards(event, selections, calculations, rounds=()):
    prizes = {p.pk: p for p in HackathonPrize.objects.filter(event=event)}
    projects = {r["snapshot_id"] for c in calculations for r in c["rows"] if r["n"]}
    seen_ranks, seen_projects = set(), set()
    for selection in selections:
        prize = prizes.get(selection["prize_id"])
        snapshot = runtime().snapshot(selection["snapshot_id"])
        if (not prize or snapshot.event_id != event.pk or snapshot.id not in projects
                or not snapshot.current or not snapshot.eligible):
            raise Http404
        from apps.events.submissions.stage_judging import require_award_stage
        require_award_stage(rounds, snapshot)  # S17: awards point at the stage their round judges.
        if prize.pk not in snapshot.prize_ids or (prize.track_id and prize.track_id not in snapshot.track_ids):
            raise ValidationError({"awards": gettext("The project is not eligible for this prize.")})
        if selection["rank"] > prize.award_count:
            raise ValidationError({"awards": gettext("This prize has fewer award slots.")})
        rank_key, project_key = (prize.pk, selection["rank"]), (prize.pk, snapshot.id)
        if rank_key in seen_ranks or project_key in seen_projects:
            raise ValidationError({"awards": gettext("Duplicate prize rank or project.")})
        seen_ranks.add(rank_key)
        seen_projects.add(project_key)
        tied = any(any(other["snapshot_id"] != snapshot.id and other["rank"] == row["rank"]
                       for other in c["rows"]) for c in calculations
                   for row in c["rows"] if row["snapshot_id"] == snapshot.id)
        if tied and not selection.get("tie_reason"):
            raise ValidationError({"awards": gettext("Record a reason for selecting a prize winner from a tie.")})
        selection["prize_name"] = prize.name
    return selections


def publish(event_id, *, actor, data):
    values = validated(PublishResultInput, data)
    with mutation(event_id, actor, permission=None) as (event, locks):
        def run():
            result = EventResultRevision.objects.filter(event=event, pk=values["result_revision_id"]).first()
            if not result:
                raise Http404
            require_version(result, values["expected_version"])
            latest = EventResultRevision.objects.filter(event=event).order_by("-version").first()
            if latest.pk != result.pk:
                invalid("Publish the latest finalized result revision.")
            for evidence in result.rounds.select_related("round").all():
                if digest(round_calculation(evidence.round)) != digest(evidence.calculation):
                    raise ProgrammeError("result_inputs_changed", "Judging eligibility changed. Create a result correction before announcing.")
            # Revalidate at release: an intervening disqualification cannot be announced.
            for award in result.awards.all():
                snapshot = runtime().snapshot(award.submission_snapshot_id)
                if not snapshot.current or not snapshot.eligible:
                    invalid("An award is no longer eligible. Create a correction.")
            prior = ResultAnnouncement.objects.filter(result=result).first()
            if not prior:
                first = ResultAnnouncement.objects.filter(event=event).order_by("published_at", "pk").first()
                at = timezone.now()
                row = ResultAnnouncement.objects.create(event=event, result=result, published_at=at, published_by=actor)
                if first is None:
                    runtime().publish_retention_locked(event_id=event_id, first_published_at=at, locks=locks)
                audit(event, actor, "results_published", row, version=result.version)
                from .options import option
                if option(event, "results_email"):  # C-37: a per-event switch, off for new events.
                    notice(event, "results_published", result.pk, result.version)
                prior = row
            state, created = ResultPublicationState.objects.get_or_create(event=event)
            if state.current_announcement_id != prior.pk:
                withdrawn = not created and state.current_announcement_id is None
                state.current_announcement = prior
                state.version += int(not created)
                state.save()
                if withdrawn:  # E-B4 (D8): published again after an unpublish; nobody is emailed twice.
                    from .results_unpublish import republish_emails
                    republish_emails(event, result, state.version)
                audit(event, actor, "result_public_pointer_updated", state, version=state.version, result_id=result.pk)
                # A paid team the corrected result no longer awards: open a recovery, never re-open the amount.
                from .prize_lineage import recoveries_for_correction_locked
                recoveries_for_correction_locked(event=event, actor=actor, new_awards=list(result.awards.select_related("prize")))
            return {"id": result.pk, "event_id": event_id, "version": result.version,
                    "state": "published", "allowed_actions": ["correct", "unpublish"]}
        return command(event, actor, values, path="results/publish", run=run)


def propose_winner_locked(*, event, actor, prize_id, snapshot_id, locks):
    from .boundary import assert_locked
    from .sponsors import require_track
    assert_locked(locks)
    prize = HackathonPrize.objects.filter(event=event, pk=prize_id, winner_selection_mode="sponsor_proposal").first()
    if not prize or not prize.sponsor_id:
        raise Http404
    snapshot = require_track(actor, event, prize.sponsor_id, snapshot_id)
    if prize.pk not in snapshot.prize_ids:
        raise Http404
    row = SponsorWinnerProposal.objects.create(event=event, prize=prize, submission_snapshot_id=snapshot.id, proposed_by=actor)
    audit(event, actor, "sponsor_winner_proposed", row, prize_id=prize.pk, snapshot_id=snapshot.id)
    return row.pk
