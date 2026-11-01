"""Member discounts: the ONE best automatic discount per quote (lane L15, A3/A4).

Candidates are the active, in-window rules of the space for this domain whose audience
matches the member: every member, the members on a plan (the member's ACTIVE membership
plan, read-only -- display titles are never tiers, A4), or that one member. The rule
that saves the most on this quote wins; ties go to the most specific audience, then the
oldest rule. Nothing else stacks: an event promo code is applied on top by the events
seam, and no line ever goes below 0.

A rule touches only discountable components (rentals, machine time, bookings,
registrations, dues) unless it names a component explicitly -- the deposit, late, damage
and lost fees are never discounted otherwise. Percent rules round half-up per line; an
amount-off rule is spread over the eligible lines, largest first.
"""

from dataclasses import replace
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.makerspaces.platform import feature_enabled
from apps.payments.pricing.components import discountable_keys
from apps.payments.pricing.quotes import ZERO, money

DISCOUNTS_FEATURE = "charges.discounts"
SPECIFICITY = {"member": 0, "plan": 1, "all_members": 2}


def member_plan_ids(makerspace, member, now=None):
    """The plans of the member's current terms here (A4). None when not a member at all."""
    from apps.makerspaces.models import MakerspaceMembership, MembershipTerm

    if member is None or not getattr(member, "is_authenticated", True):
        return None
    if not MakerspaceMembership.objects.filter(makerspace=makerspace, user=member, status="active").exists():
        return None
    now = now or timezone.now()
    return set(MembershipTerm.objects.filter(
        membership__makerspace=makerspace, membership__user=member, membership__status="active",
        status="active", starts_at__lte=now, ends_at__gt=now,
    ).values_list("plan_id", flat=True))


def candidates(makerspace, domain, member, *, now=None, audiences=None):
    from apps.payments.models_pricing_rules import PriceDiscount

    if not feature_enabled(makerspace, DISCOUNTS_FEATURE):
        return []
    now = now or timezone.now()
    rules = PriceDiscount.objects.filter(makerspace=makerspace, is_active=True, archived_at__isnull=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now), Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    if audiences is not None:
        rules = rules.filter(audience__in=audiences)
    else:
        plans = member_plan_ids(makerspace, member, now)
        if plans is None:
            return []
        rules = rules.filter(Q(audience="all_members") | Q(audience="plan", plan_id__in=plans)
                             | Q(audience="member", member=member))
    return [rule for rule in rules.order_by("pk") if not rule.domains or domain in rule.domains]


def _eligible(rule, domain, line):
    if rule.components:
        return line.component in rule.components
    return line.component in discountable_keys(domain)


def savings(rule, domain, lines, currency):
    """Per-line saving of one rule; lines already discounted keep their remaining amount only."""
    found = {}
    eligible = [(index, item) for index, item in enumerate(lines) if _eligible(rule, domain, item) and item.net > 0]
    if rule.percent_bps:
        for index, item in eligible:
            found[index] = min(money(item.net * Decimal(rule.percent_bps) / Decimal(10000), currency), item.net)
        return found
    remaining = money(rule.amount_off, currency)
    for index, item in sorted(eligible, key=lambda pair: (-pair[1].net, pair[0])):
        if remaining <= 0:
            break
        found[index] = min(remaining, item.net)
        remaining -= found[index]
    return found


def best(rules, domain, lines, currency):
    """`(rule, per-line savings)` of the single best rule, or `(None, {})`."""
    chosen, chosen_savings, chosen_key = None, {}, None
    for rule in rules:
        per_line = savings(rule, domain, lines, currency)
        total = sum(per_line.values(), ZERO)
        if total <= 0:
            continue
        key = (-total, SPECIFICITY.get(rule.audience, 3), rule.pk)
        if chosen_key is None or key < chosen_key:
            chosen, chosen_savings, chosen_key = rule, per_line, key
    return chosen, chosen_savings


def describe(rule, saving):
    return {"id": rule.pk, "name": rule.name, "audience": rule.audience, "saving": str(saving),
            "percent_bps": rule.percent_bps, "amount_off": str(rule.amount_off) if rule.amount_off else None}


def apply(quote, rule, per_line):
    if rule is None:
        return quote
    lines = tuple(replace(item, discount=item.discount + per_line.get(index, ZERO))
                  for index, item in enumerate(quote.lines))
    return replace(quote, lines=lines, discount=describe(rule, sum(per_line.values(), ZERO)))


def best_discount(makerspace, domain, member, quote, *, now=None):
    """Apply the member's best automatic discount to a quote (the public helper L6/L22 call)."""
    rule, per_line = best(candidates(makerspace, domain, member, now=now), domain, quote.lines, quote.currency)
    return apply(quote, rule, per_line)


def members_price(makerspace, domain, quote, *, now=None):
    """What an all-members rule would make this quote, for "members pay X" on a public quote."""
    rules = candidates(makerspace, domain, None, now=now, audiences=("all_members",))
    rule, per_line = best(rules, domain, quote.lines, quote.currency)
    return apply(quote, rule, per_line) if rule is not None else None
