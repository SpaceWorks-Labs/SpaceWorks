"""Paying a People's choice prize (#181 S3), by hand, exactly like a judged prize (L21b, C-38).

Only a PUBLISHED result that carries a prize can be paid, and only its winners (joint winners are
each paid once). The payout row, its L5 ledger expense, the reversal path and the winner's notice are
L21b's; the row names the winning standing instead of a judged award (the database requires exactly
one of the two). Nothing moves money automatically.
"""

from django.http import Http404
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from . import payouts
from .boundary import command, mutation
from .errors import ProgrammeError
from .models_payouts import HackathonPrizePayout
from .models_peoples_choice import PeoplesChoiceStanding
from .peoples_choice import require_live, result_for
from .ports import runtime
from .serializers import validated
from .serializers_l21b import PayoutRead
from .serializers_peoples_choice import PeoplesChoicePayoutInput


def _standing_paid(standing):
    return HackathonPrizePayout.objects.filter(peoples_choice_standing=standing, kind="payout",
                                               reversal__isnull=True).exists()


def payable(event_id, *, actor):
    from apps.events.models import Event
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None:
        raise Http404
    require_live(event)
    payouts.require_recorder(actor, event)
    result = result_for(event)
    if result is None or result.prize_id is None:
        return []
    return [{"id": row.pk, "prize_name": result.prize_name, "title": runtime().snapshot(row.submission_snapshot_id).title,
             "amount_per_winner": result.prize.amount_per_winner, "paid": _standing_paid(row)}
            for row in result.standings.filter(winner=True).order_by("pk")]


def record_payout(event_id, *, actor, data):
    values = validated(PeoplesChoicePayoutInput, data)
    # owner=True, as in L21b: the authority is RECORD_PAYMENT or MANAGE_EVENTS in the space, checked next.
    with mutation(event_id, actor, owner=True, gallery=True) as (event, _):
        require_live(event)
        payouts.require_recorder(actor, event)

        def run():
            standing = PeoplesChoiceStanding.objects.select_related("result__prize").filter(
                pk=values["standing_id"], result__event=event, winner=True).first()
            if standing is None:
                raise Http404
            prize = standing.result.prize
            if prize is None:
                raise ProgrammeError("no_prize", "This People's choice award carries no prize to pay.")
            snapshot = runtime().snapshot(standing.submission_snapshot_id)
            recipient = values.get("recipient_id") or payouts._leader(snapshot)
            if recipient not in snapshot.member_ids:
                raise ValidationError({"recipient_id": "Pay a member of the winning team."})
            if _standing_paid(standing):
                raise ProgrammeError("payout_exists", "This winner already has a recorded payout. Reverse it first.")
            if values["expected_version"] != 0:
                raise ProgrammeError("stale_version", "A new payout uses expected_version 0.", current_version=0)
            amount = values.get("amount") or prize.amount_per_winner
            if not amount:
                raise ValidationError({"amount": "This prize has no amount; enter what was paid."})
            from apps.payments.ledger_api import record_expense
            from .options import currency
            money = currency(event.makerspace)
            attempt = HackathonPrizePayout.objects.filter(peoples_choice_standing=standing, kind="payout").count() + 1
            payout = HackathonPrizePayout(makerspace=event.makerspace, event=event, peoples_choice_standing=standing,
                                          prize=prize, recipient_id=recipient, amount=amount, currency=money,
                                          method=values["method"], reference=values["reference"],
                                          paid_on=values["paid_on"], recorded_by=actor)
            payout.ledger_entry = record_expense(
                event.makerspace, "events", None, amount, money, values["method"], values["reference"],
                values.get("receipt_id"), payouts.SOURCE_KIND, f"peoples_choice:{standing.pk}:{attempt}", actor,
                category="prize", description=f"Prize: {standing.result.prize_name}"[:300],
                entry_date=values["paid_on"], event=event)
            payout.save()
            record(actor, "event.prize.payout_recorded", makerspace=event.makerspace, target=payout,
                   meta={"event_id": event.pk, "peoples_choice_standing_id": standing.pk, "prize_id": prize.pk,
                         "ledger_entry_id": payout.ledger_entry_id})
            from .payout_notices import payout_recorded_notice
            payout_recorded_notice(payout)
            return PayoutRead(payouts.projection(payout)).data
        return command(event, actor, values, path="peoples-choice/payouts", run=run)
