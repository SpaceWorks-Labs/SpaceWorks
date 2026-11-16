"""Decision 223 (k), lane L3b: approved volunteer hours become a recorded membership credit.

Conversion. The policy says "N hours earn a discount amount (or free days)". `convert_available_minutes`
turns approved minutes that no credit has consumed yet into whole credits of `volunteer_minutes_per_credit`
each; the remainder keeps waiting. It runs under the member's row lock so two approvals cannot mint the same
credit twice.

Application (the membership charge path). `reduce_charge` is called by the two seams that raise a membership
term charge (`membership_term_charges`, `membership_renewal_charges`) BEFORE they record the debt. It
returns the net amount to record; each credit it uses is stamped with the payment afterwards by
`stamp_applied`. A credit is therefore a visible, audited ledger row (who, how many hours, how much, which
charge), never a silent price change, and it works with the payments rail off. A credit larger than the
charge is split: the used part is stamped, the remainder stays available.

Free days are applied as a prorated reduction (`days / term length` of the term price), the cleanest way to
express "free days" without moving a term's dates (auto decision).
"""
import math
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.community_policy import policy_for, volunteer_on
from apps.makerspaces.models import VolunteerCredit, VolunteerHourEntry
from apps.payments.money import quantize_money


def _consumed_minutes(makerspace, member):
    # A VOID credit still consumed its minutes: excluding it re-minted the voided credit on the
    # next conversion, which made "void" a no-op (final audit 0.12.0).
    return VolunteerCredit.objects.filter(makerspace=makerspace, member=member).aggregate(
        total=Sum("minutes_converted"))["total"] or 0


def convert_available_minutes(actor, makerspace, member, currency=""):
    """Mint credits for whole blocks of approved, unconverted minutes. Returns the new credits."""
    policy = policy_for(makerspace)
    block = policy.volunteer_minutes_per_credit
    value = policy.volunteer_credit_amount if policy.volunteer_credit_kind == "discount" else policy.volunteer_credit_days
    if not volunteer_on(makerspace) or block <= 0 or not value:
        return []
    created = []
    if not currency and policy.volunteer_credit_kind == "discount":
        # m22: a currency-less discount would apply to a charge in any currency; pin it to the space default.
        from apps.payments.models import MakerspacePaymentSettings
        currency = MakerspacePaymentSettings.for_makerspace(makerspace).default_currency
    with transaction.atomic():
        from apps.accounts.models import User
        User.objects.select_for_update().get(pk=member.pk)
        approved = VolunteerHourEntry.objects.filter(
            makerspace=makerspace, member=member, status=VolunteerHourEntry.Status.APPROVED,
        ).aggregate(total=Sum("minutes"))["total"] or 0
        blocks = (approved - _consumed_minutes(makerspace, member)) // block
        for _ in range(max(0, blocks)):
            credit = VolunteerCredit.objects.create(
                makerspace=makerspace, member=member, minutes_converted=block, kind=policy.volunteer_credit_kind,
                amount=policy.volunteer_credit_amount if policy.volunteer_credit_kind == "discount" else 0,
                days=policy.volunteer_credit_days if policy.volunteer_credit_kind == "free_days" else 0,
                currency=(currency or "").lower(), created_by=actor)
            audit.record(actor, "membership.volunteer_credit_created", makerspace=makerspace, target=credit,
                         meta={"minutes": block, "kind": credit.kind})
            created.append(credit)
    return created


def available_credits(makerspace, member):
    return VolunteerCredit.objects.filter(
        makerspace=makerspace, member=member, status=VolunteerCredit.Status.AVAILABLE)


def reduce_charge(makerspace, member, gross, currency, *, term_days, floor=Decimal("0")):
    """`(net_amount, used)` for one membership charge. `used` is a list of `(credit_id, applied_amount)`.

    Call inside the caller's transaction, before `create_payment`. With the capability off, no credits, or a
    non-positive gross, the charge is returned unchanged.
    """
    gross = Decimal(gross)
    if not volunteer_on(makerspace) or gross <= 0:
        return gross, []
    remaining, used = gross, []
    gross_floor = Decimal(floor)
    daily = quantize_money(gross / Decimal(max(1, term_days)), currency, ROUND_HALF_UP)
    for credit in available_credits(makerspace, member).select_for_update().order_by("created_at", "pk"):
        if remaining <= gross_floor:
            break
        if credit.currency and credit.currency != (currency or "").lower():
            continue
        if credit.kind == "discount":
            worth = Decimal(credit.amount)
        else:
            worth = quantize_money(daily * credit.days, currency, ROUND_HALF_UP)
        take = min(worth, remaining - gross_floor)
        if take <= 0:
            continue
        if take < worth:
            _split(credit, worth - take, daily)
        used.append((credit.pk, take))
        remaining -= take
    return quantize_money(remaining, currency), used


def _split(credit, left_value, daily):
    """Leave the unused part of a credit available as a new row; the original is stamped when applied."""
    days = 0 if credit.kind == "discount" else min(credit.days, math.ceil(left_value / daily)) if daily else 0
    VolunteerCredit.objects.create(
        makerspace=credit.makerspace, member=credit.member, minutes_converted=0, kind=credit.kind,
        amount=left_value if credit.kind == "discount" else 0, days=days, currency=credit.currency,
        split_from=credit, created_by=credit.created_by)


def stamp_applied(actor, makerspace, used, payment):
    """Record on each used credit the charge it reduced, and audit it. `used` comes from `reduce_charge`."""
    now = timezone.now()
    for credit_id, amount in used:
        credit = VolunteerCredit.objects.select_for_update().get(pk=credit_id)
        credit.status, credit.applied_payment, credit.applied_amount, credit.applied_at = (
            VolunteerCredit.Status.USED, payment, amount, now)
        credit.save(update_fields=["status", "applied_payment", "applied_amount", "applied_at"])
        audit.record(actor, "membership.volunteer_credit_applied", makerspace=makerspace, target=credit,
                     meta={"payment_id": getattr(payment, "pk", None), "applied_amount": str(amount)})


def void_credit(actor, credit, reason):
    with transaction.atomic():
        row = VolunteerCredit.objects.select_for_update().select_related("makerspace").get(pk=credit.pk)
        if row.status == VolunteerCredit.Status.AVAILABLE:
            row.status, row.void_reason = VolunteerCredit.Status.VOID, (reason or "").strip()[:200]
            row.save(update_fields=["status", "void_reason"])
            audit.record(actor, "membership.volunteer_credit_voided", makerspace=row.makerspace, target=row)
    return row
