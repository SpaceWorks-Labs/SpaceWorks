"""L21b (C-38): prize payouts, recorded by hand. Nothing is ever paid automatically.

Who records: a holder of RECORD_PAYMENT in the space, or the Event Manager (MANAGE_EVENTS). Each
payout writes one L5 ledger expense (domain ``events``, category ``prize``) in the same transaction.
Rows are append-only; a mistake is corrected with a reversal row, which voids that ledger expense.
A winner of a PUBLISHED result is paid at most once while a payout stands.
"""

from django.http import Http404
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError
from .models_payouts import HackathonPrizePayout
from .models_results import EventAward, ResultPublicationState
from .ports import runtime
from .serializers import validated
from .serializers_l21b import PayoutInput, PayoutReverseInput

SOURCE_KIND = "events.prize_payout"


def may_record(actor, makerspace_id):
    return (rbac.can(actor, rbac.Action.RECORD_PAYMENT, makerspace_id)
            or rbac.can(actor, rbac.Action.MANAGE_EVENTS, makerspace_id))


def require_recorder(actor, event):
    from .feature import PRIZE_PAYOUTS, require_capability
    require_capability(event, PRIZE_PAYOUTS)
    if not may_record(actor, event.makerspace_id):
        raise Http404  # Never disclose an event to someone who may not record its money.


def _published_award(event, award_id):
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement").first()
    if state is None or state.current_announcement_id is None:
        raise ProgrammeError("results_unpublished", "Prizes are paid only for published results.")
    award = EventAward.objects.select_related("prize").filter(
        pk=award_id, result_id=state.current_announcement.result_id, result__event=event).first()
    if award is None:
        raise Http404
    return award


def record_payout(event_id, *, actor, data):
    values = validated(PayoutInput, data)
    from .prize_access import read_key
    from .prize_claims import runtime_event
    # owner=True: the authority here is RECORD_PAYMENT or MANAGE_EVENTS in the space (C-38), checked next.
    # read_key: best effort, so a paid winner's routing details can be cleared (G4).
    with read_key(runtime_event(event_id).makerspace_id), mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)

        def run():
            award = _published_award(event, values["award_id"])
            _require_payable(award)
            snapshot = runtime().snapshot(award.submission_snapshot_id)
            recipient = values.get("recipient_id") or _leader(snapshot)
            if recipient not in snapshot.member_ids:
                raise ValidationError({"recipient_id": "Pay a member of the winning team."})
            if values["expected_version"] != 0:
                raise ProgrammeError("stale_version", "A new payout uses expected_version 0.", current_version=0)
            from .payout_split import payout_amount
            amount = payout_amount(award, recipient, values.get("amount"))
            from .prize_tax import proposed_tds
            tds = values["tds_amount"] if values.get("tds_amount") is not None else proposed_tds(event.makerspace, amount)
            if tds >= amount:
                raise ValidationError({"tds_amount": "Tax deducted must be less than the gross prize."})
            from apps.payments.ledger_api import record_expense
            from .options import currency
            money = currency(event.makerspace)
            payout = HackathonPrizePayout(makerspace=event.makerspace, event=event, award=award, prize=award.prize,
                                          recipient_id=recipient, amount=amount, tds_amount=tds,
                                          net_amount=amount - tds, currency=money,
                                          method=values["method"], reference=values["reference"],
                                          paid_on=values["paid_on"], recorded_by=actor)
            # A LedgerConflict (409) rolls the whole payout back with the event transaction.
            payout.ledger_entry = record_expense(
                event.makerspace, "events", None, amount, money, values["method"], values["reference"],
                values.get("receipt_id"), SOURCE_KIND, f"award:{award.pk}:{_attempt(award)}", actor,
                category="prize", description=_description(award, tds, money), entry_date=values["paid_on"],
                event=event)
            payout.save()
            from .models_prize_money import HackathonPrizeShare
            from .prize_claims import clear_locked
            for share in HackathonPrizeShare.objects.filter(award=award, member_id=recipient):
                clear_locked(share)
            record(actor, "event.prize.payout_recorded", makerspace=event.makerspace, target=payout,
                   meta={"event_id": event.pk, "award_id": award.pk, "prize_id": award.prize_id,
                         "ledger_entry_id": payout.ledger_entry_id})
            from .payout_notices import payout_recorded_notice
            payout_recorded_notice(payout)
            return projection(payout)
        return command(event, actor, values, path="prize-payouts", run=run)


def _require_payable(award):
    """Hack-money G5/G8: only a cash prize the space pays is a payout; the rest are fulfilled."""
    if award.prize.funding == "sponsor_direct":
        raise ProgrammeError("sponsor_direct", "The sponsor pays this prize directly; record it as fulfilled.")
    if award.prize.kind != "cash":
        raise ProgrammeError("non_cash_prize", "Record a non-cash prize as handed over or shipped.")
    from .models_prize_money import HackathonPrizeOutcome
    if HackathonPrizeOutcome.objects.filter(award=award, share__isnull=True,
                                            kind__in=("fulfilled", "sponsor_paid", "forfeited")).exists():
        raise ProgrammeError("already_settled", "This prize is already settled.")


def _description(award, tds, currency):
    """The ledger records the GROSS prize; a deduction is a memo for staff who file it outside SpaceWorks."""
    memo = f" (gross; tax deducted {tds} {currency.upper()})" if tds else ""
    return f"Prize: {award.prize_name}{memo}"[:300]


def _leader(snapshot):
    from apps.events.models import HackathonTeam
    leader = HackathonTeam.objects.filter(pk=snapshot.team_id).values_list("leader_id", flat=True).first()
    return leader if leader in snapshot.member_ids else (snapshot.member_ids[0] if snapshot.member_ids else None)


def _attempt(award):
    """Each payout after a reversal is a new ledger source, so the reversed expense stays void."""
    return HackathonPrizePayout.objects.filter(award=award, kind="payout").count() + 1


def reverse_payout(event_id, payout_id, *, actor, data):
    values = validated(PayoutReverseInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)

        def run():
            payout = HackathonPrizePayout.objects.select_for_update().filter(
                event=event, pk=payout_id, kind="payout").first()
            if payout is None:
                raise Http404
            if values["expected_version"] != 0:
                raise ProgrammeError("stale_version", "Reversals use expected_version 0.", current_version=0)
            if HackathonPrizePayout.objects.filter(reverses=payout).exists():
                raise ProgrammeError("already_reversed", "This payout is already reversed.")
            from apps.payments.ledger_api import void
            void(payout.ledger_entry, actor, values["reason"])
            row = HackathonPrizePayout.objects.create(
                makerspace=event.makerspace, event=event, award=payout.award, prize=payout.prize,
                recipient_id=payout.recipient_id, kind="reversal", reverses=payout, amount=payout.amount,
                tds_amount=payout.tds_amount, net_amount=payout.net_amount, currency=payout.currency, method=payout.method, reference=payout.reference, paid_on=payout.paid_on,
                ledger_entry=payout.ledger_entry, recorded_by=actor)
            record(actor, "event.prize.payout_reversed", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "payout_id": payout.pk, "ledger_entry_id": payout.ledger_entry_id})
            return projection(row)
        return command(event, actor, values, path=f"prize-payouts/{payout_id}/reverse", run=run)


def listing(event_id, *, actor):
    from apps.events import event_authority
    from apps.events.models import Event
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None or not (event_authority.can(actor, event, "manage_hackathon") or may_record(actor, event.makerspace_id)):
        raise Http404
    runtime().require_programme(event)
    from .feature import PRIZE_PAYOUTS, require_capability
    require_capability(event, PRIZE_PAYOUTS)
    rows = HackathonPrizePayout.objects.filter(event=event).select_related("award").order_by("-pk")
    return [projection(row, recorder=may_record(actor, event.makerspace_id)) for row in rows], payable_awards(event)


def payable_awards(event):
    """The announced result's awards with their prize amount and whether a payout stands."""
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement").first()
    if state is None or state.current_announcement_id is None:
        return []
    paid = set(HackathonPrizePayout.objects.filter(event=event, kind="payout", reversal__isnull=True)
               .values_list("award_id", flat=True))
    from .payout_split import award_extras
    return [{"id": award.pk, "prize_name": award.prize_name, "rank": award.rank,
             "title": runtime().snapshot(award.submission_snapshot_id).title,
             "amount_per_winner": award.prize.amount_per_winner, "paid": award.pk in paid, **award_extras(award)}
            for award in EventAward.objects.select_related("prize").filter(
                result_id=state.current_announcement.result_id).order_by("prize_id", "rank")]


def projection(row, *, recorder=True):
    reversible = recorder and row.kind == "payout" and not HackathonPrizePayout.objects.filter(reverses=row).exists()
    return {"id": row.pk, "event_id": row.event_id, "award_id": row.award_id, "prize_id": row.prize_id,
            "prize_name": row.award.prize_name, "recipient_id": row.recipient_id, "kind": row.kind,
            "reverses_id": row.reverses_id, "amount": row.amount, "tds_amount": row.tds_amount,
            "net_amount": row.net_amount if row.net_amount is not None else row.amount - row.tds_amount,
            "currency": row.currency, "method": row.method,
            "reference": row.reference, "paid_on": row.paid_on, "ledger_entry_id": row.ledger_entry_id,
            "created_at": row.created_at, "allowed_actions": ["reverse"] if reversible else []}
