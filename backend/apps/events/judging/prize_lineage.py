"""Hack-money: a prize payment is bound to (prize, winning team), not to one award row.

A results correction creates NEW `EventAward` rows (append-only history). Keyed on the award row alone,
a prize that was already paid read as owed again on the corrected result and `record_payout` could pay
it twice. Every "was this paid / split / settled" check therefore asks about the award's LINEAGE: every
award of the event that names the same prize and the same team, across all result revisions.

A correction that drops a paid team from a prize cannot take the money back: it opens a recovery
(`recovery_opened`, the same row a post-payout disqualification opens) instead of silently re-opening
the amount. Nothing here moves money.
"""

from .models_payouts import HackathonPrizePayout
from .models_prize_money import HackathonPrizeOutcome
from .models_results import EventAward
from .ports import runtime


def _team(award):
    return runtime().snapshot(award.submission_snapshot_id).team_id


def lineage_ids(award):
    """This award's pk plus every other award of the same prize and team in the event, any revision."""
    ids = [award.pk]
    team = _team(award)
    others = EventAward.objects.filter(prize_id=award.prize_id, result__event_id=award.result.event_id).exclude(pk=award.pk)
    return ids + [other.pk for other in others if _team(other) == team]


def standing_payouts(award):
    return HackathonPrizePayout.objects.filter(award_id__in=lineage_ids(award), kind="payout", reversal__isnull=True)


def recoveries_for_correction_locked(*, event, actor, new_awards):
    """Inside the correcting transaction: a standing payout whose (prize, team) is no longer awarded opens a recovery."""
    from .prize_outcomes import open_recovery_row
    kept = {(award.prize_id, _team(award)) for award in new_awards}
    opened = []
    payouts = HackathonPrizePayout.objects.filter(event=event, kind="payout", reversal__isnull=True,
                                                  award__isnull=False).select_related("award__result")
    for payout in payouts.order_by("pk"):
        if (payout.prize_id, _team(payout.award)) in kept:
            continue
        if HackathonPrizeOutcome.objects.filter(payout=payout, kind="recovery_opened").exists():
            continue
        opened.append(open_recovery_row(event=event, payout=payout, actor=actor, note="Result corrected after payout",
                                        reason="result_corrected"))
    return opened
