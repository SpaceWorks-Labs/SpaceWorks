"""Hack-money G6: "Prizes owed", the announced awards a space has not settled yet.

One row per award of an event's CURRENT published result whose prize is not paid, fulfilled,
sponsor-paid or forfeited, plus every award with an open recovery (money owed back after a
disqualification, G16); People's choice winners (#181) appear the same way. Names no winner and no payee: only the event, prize, rank, kind, amount
outstanding and the claim deadline. Behind `events.prize_payouts`; never combined across an
organization (each space's own prizes and books).
"""

from decimal import Decimal

from apps.operations.report_types import ReportResult

FIELDS = ("event_id", "event", "prize", "rank", "kind", "funding", "status", "currency", "amount_outstanding",
          "open_recoveries", "claim_deadline")
OPEN = ("owed", "part_paid")


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids
    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def _outstanding(award, status):
    from django.db.models import Sum
    from apps.events.judging.models_payouts import HackathonPrizePayout
    prize = award.prize
    if prize.kind != "cash" or prize.funding != "space" or status not in OPEN:
        return None
    paid = HackathonPrizePayout.objects.filter(award=award, kind="payout", reversal__isnull=True).aggregate(
        total=Sum("amount"))["total"] or Decimal("0")
    return max((prize.amount_per_winner or Decimal("0")) - paid, Decimal("0"))


def rows_for(space):
    from apps.events.judging.models_prize_money import HackathonPrizeOutcome
    from apps.events.judging.options import currency
    from apps.events.judging.payout_split import award_status
    from apps.events.judging.prize_claims import claim_deadline
    from apps.events.judging.prize_reads import current_awards
    from apps.events.models import Event
    money = currency(space)
    rows = []
    for event in Event.objects.filter(makerspace=space).order_by("starts_at", "pk"):
        deadline = None
        for award in current_awards(event).order_by("prize_id", "rank"):
            status = award_status(award)
            recoveries = HackathonPrizeOutcome.objects.filter(award=award, kind="recovery_opened",
                                                              resolution__isnull=True).count()
            if status not in OPEN and not recoveries:
                continue
            deadline = deadline or claim_deadline(event)
            outstanding = _outstanding(award, status)
            rows.append({"event_id": event.pk, "event": event.title, "prize": award.prize_name, "rank": award.rank,
                         "kind": award.prize.kind, "funding": award.prize.funding, "status": status,
                         "currency": money, "amount_outstanding": outstanding, "open_recoveries": recoveries,
                         "claim_deadline": deadline.isoformat() if deadline else None})
        # #181: People's choice winners owe or are owed like judged awards (no winner named).
        from apps.events.judging.peoples_choice_money import report_rows
        rows.extend(report_rows(event, money, lambda: deadline or claim_deadline(event)))
    return rows


def build_prizes_owed(makerspace_id, *, limit=None, date_range=None):
    records = []
    for space in _spaces(makerspace_id):
        records.extend(rows_for(space))
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Announced prizes not yet paid, handed over or forfeited, and prizes owed back after a "
                      "disqualification. Payouts are recorded by hand; nothing here moves money.",
        "columns": "amount_outstanding = prize amount less standing payouts (cash prizes the space pays only).",
    })
