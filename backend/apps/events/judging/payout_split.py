"""Hack-money G3/G5/G7/G8/G16: how a recorded payout fits an award's split, and what staff see per award.

- No shares: the L21b rule stands. One standing payout per award, default amount the prize amount.
- Shares: each CONFIRMED share is paid by its own payout to its member (default amount the share),
  at most once while a payout stands; a proposed, declined or forfeited share cannot be paid; and
  the standing payouts of an award never add up to more than the prize amount.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from .errors import ProgrammeError
from .models_payouts import HackathonPrizePayout
from .models_prize_money import HackathonPrizeOutcome, HackathonPrizeShare


def _standing(award):
    """Standing payouts of this award's lineage: a results correction never re-opens a paid amount."""
    from .prize_lineage import standing_payouts
    return standing_payouts(award)


def lineage_shares(award):
    from .prize_lineage import lineage_ids
    return HackathonPrizeShare.objects.filter(award_id__in=lineage_ids(award))


def payout_amount(award, recipient, entered):
    shares = lineage_shares(award)
    if not shares.exists():
        if _standing(award).exists():
            raise ProgrammeError("payout_exists", "This award already has a recorded payout. Reverse it first.")
        amount = entered or award.prize.amount_per_winner
        if not amount:
            raise ValidationError({"amount": gettext("This prize has no amount; enter what was paid.")})
        return Decimal(amount)
    share = shares.filter(member_id=recipient).first()
    if share is None or share.state != "confirmed":
        raise ProgrammeError("share_not_confirmed", "Pay a member whose share is confirmed.")
    if _standing(award).filter(recipient_id=recipient).exists():
        raise ProgrammeError("payout_exists", "This share already has a recorded payout. Reverse it first.")
    amount = Decimal(entered or share.amount)
    ceiling = award.prize.amount_per_winner or shares.aggregate(total=Sum("amount"))["total"]
    paid = _standing(award).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if paid + amount > ceiling:
        raise ValidationError({"amount": gettext('Payouts for this prize would exceed its amount ({ceiling}).').format(ceiling=ceiling)})
    return amount


def award_status(award):
    """owed | paid | part_paid | fulfilled | sponsor_paid | forfeited, plus an open recovery flag."""
    from .prize_lineage import lineage_ids
    outcomes = set(HackathonPrizeOutcome.objects.filter(award_id__in=lineage_ids(award)).values_list("kind", flat=True))
    standing = _standing(award)
    shares = lineage_shares(award).exclude(state__in=("declined", "forfeited"))
    for kind in ("fulfilled", "sponsor_paid"):
        if kind in outcomes:
            return kind
    if standing.exists():
        unpaid = shares.exclude(member_id__in=standing.values("recipient_id")).exists()
        return "part_paid" if unpaid else "paid"
    return "forfeited" if "forfeited" in outcomes else "owed"


def owed_amount(award):
    """What the space still owes on a cash award: all of it when unpaid, the unpaid live shares when part paid."""
    status = award_status(award)
    if status == "owed":
        return award.prize.amount_per_winner or Decimal("0")
    if status != "part_paid":
        return Decimal("0")
    unpaid = lineage_shares(award).exclude(state__in=("declined", "forfeited")).exclude(
        member_id__in=_standing(award).values("recipient_id"))
    return unpaid.aggregate(total=Sum("amount"))["total"] or Decimal("0")


def award_extras(award):
    from .prize_tax import tax_settings
    prize = award.prize
    shares = lineage_shares(award).order_by("pk")
    paid_to = set(_standing(award).values_list("recipient_id", flat=True))
    from .prize_lineage import lineage_ids
    recoveries = HackathonPrizeOutcome.objects.filter(award_id__in=lineage_ids(award), kind="recovery_opened",
                                                      resolution__isnull=True)
    tax = tax_settings(award.prize.event.makerspace)
    return {"kind": prize.kind, "funding": prize.funding, "value_text": prize.value_text,
            "status": award_status(award), "open_recoveries": recoveries.count(),
            "tax_proposal": {"enabled": tax.prize_tds_enabled, "rate": tax.prize_tds_rate,
                             "threshold": tax.prize_tds_threshold},
            "shares": [{"id": row.pk, "member_id": row.member_id, "amount": row.amount, "state": row.state,
                        "paid": row.member_id in paid_to} for row in shares]}
