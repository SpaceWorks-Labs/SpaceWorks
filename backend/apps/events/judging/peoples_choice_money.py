"""People's choice prize money under the judged-prize rules (#181 S3 with hack-money G6/G7/G16).

A published People's choice result that carries a cash prize the space pays is owed to each winning
standing until a payout stands, exactly like a judged award: it counts in the prize pool's "owed"
total and the "Prizes owed" report, and a later disqualification opens a recovery on its payout.
"""

from decimal import Decimal

from .models_payouts import HackathonPrizePayout

ZERO = Decimal("0")


def published_prize(event):
    """(result, prize) for a published result that carries a prize, else (None, None)."""
    from .models_peoples_choice import PeoplesChoiceResult
    result = PeoplesChoiceResult.objects.filter(event=event).select_related("prize").first()
    if result is None or result.prize_id is None:
        return None, None
    return result, result.prize


def standing_paid(standing):
    return HackathonPrizePayout.objects.filter(peoples_choice_standing=standing, kind="payout",
                                               reversal__isnull=True).exists()


def is_space_cash(prize):
    return prize is not None and prize.kind == "cash" and prize.funding == "space" and bool(prize.amount_per_winner)


def unpaid_winners(event):
    """Winning standings of a published cash prize the space pays, with no standing payout."""
    result, prize = published_prize(event)
    if not is_space_cash(prize):
        return []
    return [row for row in result.standings.filter(winner=True).order_by("pk") if not standing_paid(row)]


def owed(event):
    _result, prize = published_prize(event)
    return (prize.amount_per_winner or ZERO) * len(unpaid_winners(event)) if is_space_cash(prize) else ZERO


def open_recoveries(standing):
    from .models_prize_money import HackathonPrizeOutcome
    return HackathonPrizeOutcome.objects.filter(payout__peoples_choice_standing=standing, kind="recovery_opened",
                                                resolution__isnull=True).count()


def report_rows(event, money, deadline_for):
    """Prizes-owed rows for People's choice winners: unpaid, or with money owed back. Names no winner."""
    result, prize = published_prize(event)
    if result is None:
        return []
    unpaid = {row.pk for row in unpaid_winners(event)}
    rows, deadline = [], None
    for standing in result.standings.filter(winner=True).order_by("pk"):
        recoveries = open_recoveries(standing)
        if standing.pk not in unpaid and not recoveries:
            continue
        deadline = deadline or deadline_for()
        rows.append({"event_id": event.pk, "event": event.title, "prize": result.prize_name, "rank": standing.rank,
                     "kind": prize.kind, "funding": prize.funding,
                     "status": "owed" if standing.pk in unpaid else "paid", "currency": money,
                     "amount_outstanding": prize.amount_per_winner if standing.pk in unpaid else None,
                     "open_recoveries": recoveries, "claim_deadline": deadline.isoformat() if deadline else None})
    return rows


def tax_proposal(makerspace):
    from .prize_tax import tax_settings
    tax = tax_settings(makerspace)
    return {"enabled": tax.prize_tds_enabled, "rate": tax.prize_tds_rate, "threshold": tax.prize_tds_threshold}
