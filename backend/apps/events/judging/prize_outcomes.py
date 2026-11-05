"""Hack-money prize outcomes that are not payouts (append-only `HackathonPrizeOutcome` rows).

- G5 `fulfilled`: a non-cash prize (item, credit, perk) handed over or shipped. No ledger entry: if
  the space bought the item it recorded that purchase as an ordinary expense when it bought it.
- G8 `sponsor_paid`: a `sponsor_direct` prize the sponsor paid the winner itself. No expense.
- G4 `forfeited`: an unpaid prize after the claim window, by staff decision. No ledger effect at
  all, because no expense was ever recorded.
- G16 `recovery_opened` / `recovery_repaid` / `recovery_waived`: a winner disqualified AFTER a
  payout owes the money back. Opening never charges anyone; when staff record that it was repaid,
  a ledger RECEIPT (domain events, category prize_recovery) is written in the same transaction.

Who records: RECORD_PAYMENT holders or the Event Manager (C-38), behind `events.prize_payouts`.
"""

from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError
from .models_payouts import HackathonPrizePayout
from .models_prize_money import HackathonPrizeOutcome, HackathonPrizeShare
from .serializers import validated
from .serializers_prize import ForfeitInput, FulfilInput, RecoveryResolveInput

SOURCE_KIND = "events.prize_recovery"


def _award(event, award_id):
    from .payouts import _published_award
    return _published_award(event, award_id)


def _row(event, award, kind, actor, **values):
    return HackathonPrizeOutcome.objects.create(makerspace=event.makerspace, event=event, award=award, kind=kind,
                                                recorded_by=actor, happened_on=values.pop("happened_on", None)
                                                or timezone.localdate(), **values)


def _settled(award):
    """An award is settled once paid (a standing payout), fulfilled, sponsor-paid or forfeited."""
    paid = HackathonPrizePayout.objects.filter(award=award, kind="payout", reversal__isnull=True).exists()
    return paid or HackathonPrizeOutcome.objects.filter(award=award, kind__in=("fulfilled", "sponsor_paid",
                                                                               "forfeited")).exists()


def fulfil(event_id, award_id, *, actor, data):
    """G5/G8: record a non-cash prize handed over or shipped, or a sponsor's direct payment."""
    from .payouts import require_recorder
    values = validated(FulfilInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)

        def run():
            award = _award(event, award_id)
            prize = award.prize
            kind = "sponsor_paid" if prize.funding == "sponsor_direct" else "fulfilled"
            if kind == "fulfilled" and prize.kind == "cash":
                raise ProgrammeError("cash_prize", "Record a cash prize the space pays as a payout.")
            if _settled(award):
                raise ProgrammeError("already_settled", "This prize is already settled.")
            row = _row(event, award, kind, actor, method=values["method"], reference=values.get("reference", ""),
                       note=values.get("note", ""), happened_on=values["happened_on"])
            record(actor, "event.prize.sponsor_paid" if kind == "sponsor_paid" else "event.prize.fulfilled",
                   makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "award_id": award.pk, "outcome_id": row.pk})
            return projection(row)
        return command(event, actor, values, path=f"prize-awards/{award_id}/fulfil", run=run)


def forfeit(event_id, award_id, *, actor, data):
    """G4: after the claim window, staff mark an unpaid prize (or one unpaid share) forfeited."""
    from .payouts import require_recorder
    from .prize_claims import claim_deadline
    from .prize_access import read_key
    from .prize_claims import clear_locked, runtime_event
    values = validated(ForfeitInput, data)
    with read_key(runtime_event(event_id).makerspace_id), mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)

        def run():
            award = _award(event, award_id)
            deadline = claim_deadline(event)
            if deadline is None or timezone.now() <= deadline:
                raise ProgrammeError("claim_window_open", "A prize is forfeited only after its claim window closes.")
            share = None
            if values.get("share_id"):
                share = HackathonPrizeShare.objects.select_for_update().filter(award=award, pk=values["share_id"]).first()
                if share is None:
                    raise Http404
                if HackathonPrizePayout.objects.filter(award=award, recipient_id=share.member_id, kind="payout",
                                                       reversal__isnull=True).exists():
                    raise ProgrammeError("already_settled", "This share was paid.")
                share.state, share.version = "forfeited", share.version + 1
                share.save()
                clear_locked(share, pan=True)
            elif _settled(award):
                raise ProgrammeError("already_settled", "This prize is already settled.")
            else:
                for unpaid in HackathonPrizeShare.objects.filter(award=award):
                    clear_locked(unpaid, pan=True)
            row = _row(event, award, "forfeited", actor, share=share, note=values["note"])
            record(actor, "event.prize.forfeited", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "award_id": award.pk, "outcome_id": row.pk,
                         "share_id": share.pk if share else None})
            return projection(row)
        return command(event, actor, values, path=f"prize-awards/{award_id}/forfeit", run=run)


def open_recoveries_locked(*, event, project, actor):
    """G16, inside the disqualifying transaction: every standing payout to this project's winning
    snapshots opens one recovery (amount owed back). It never charges the member."""
    from .models_results import EventAward
    from apps.events.models import SubmissionSnapshot
    snapshots = SubmissionSnapshot.objects.filter(submission_id=project.pk).values("pk")
    awards = EventAward.objects.filter(submission_snapshot_id__in=snapshots).values("pk")
    payouts = HackathonPrizePayout.objects.filter(event=event, award_id__in=awards, kind="payout",
                                                  reversal__isnull=True).select_related("award")
    opened = []
    for payout in payouts.order_by("pk"):
        if HackathonPrizeOutcome.objects.filter(payout=payout, kind="recovery_opened").exists():
            continue
        row = _row(event, payout.award, "recovery_opened", actor, payout=payout, amount=payout.amount,
                   currency=payout.currency, note="Disqualified after payout")
        record(actor, "event.prize.recovery_opened", makerspace=event.makerspace, target=row,
               meta={"event_id": event.pk, "award_id": payout.award_id, "payout_id": payout.pk, "outcome_id": row.pk})
        opened.append(row)
    return opened


def resolve_recovery(event_id, outcome_id, *, actor, data):
    """G16: record that the money came back (a ledger receipt) or waive it, with a note."""
    from .payouts import require_recorder
    values = validated(RecoveryResolveInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)

        def run():
            opened = HackathonPrizeOutcome.objects.select_related("award", "payout").filter(
                event=event, pk=outcome_id, kind="recovery_opened").first()
            if opened is None:
                raise Http404
            if HackathonPrizeOutcome.objects.filter(resolves=opened).exists():
                raise ProgrammeError("already_resolved", "This recovery is already closed.")
            entry = None
            if values["outcome"] == "repaid":
                from apps.payments.ledger_api import record_receipt
                entry = record_receipt(event.makerspace, "events", None, opened.amount, opened.currency,
                                       values["method"], values.get("reference", ""), values.get("receipt_id"),
                                       SOURCE_KIND, f"outcome:{opened.pk}", actor, category="prize_recovery",
                                       description=f"Prize repaid: {opened.award.prize_name}"[:300],
                                       entry_date=values["happened_on"], event=event)
            kind = "recovery_repaid" if entry is not None else "recovery_waived"
            row = _row(event, opened.award, kind, actor, payout=opened.payout, resolves=opened, amount=opened.amount,
                       currency=opened.currency, method=values.get("method", ""), reference=values.get("reference", ""),
                       note=values.get("note", ""), happened_on=values["happened_on"], ledger_entry=entry)
            record(actor, "event.prize.recovery_repaid" if entry is not None else "event.prize.recovery_waived",
                   makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "outcome_id": row.pk, "ledger_entry_id": entry.pk if entry else None})
            return projection(row)
        return command(event, actor, values, path=f"prize-outcomes/{outcome_id}/resolve", run=run)


def projection(row):
    resolved = row.kind == "recovery_opened" and HackathonPrizeOutcome.objects.filter(resolves=row).exists()
    return {"id": row.pk, "event_id": row.event_id, "award_id": row.award_id, "share_id": row.share_id,
            "payout_id": row.payout_id, "resolves_id": row.resolves_id, "kind": row.kind, "method": row.method,
            "reference": row.reference, "amount": row.amount, "currency": row.currency, "happened_on": row.happened_on,
            "note": row.note, "ledger_entry_id": row.ledger_entry_id, "created_at": row.created_at,
            "allowed_actions": ["resolve"] if row.kind == "recovery_opened" and not resolved else []}


def listing(event):
    return [projection(row) for row in HackathonPrizeOutcome.objects.filter(event=event).order_by("-pk")]
