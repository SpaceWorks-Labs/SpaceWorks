"""Discount rules: create, change, archive (lane L15, A3/A4). Space Manager only.

Discounts are space-wide money policy, so they are a finance setting (`charges` module)
and never delegable: `assert_setting_write` refuses anyone but the Space Manager with
`setting_not_delegated`. Rules are archived, never deleted -- a frozen quote names the
rule it applied. Every write is atomic, audited and refused during a tenant move.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.payments.models_pricing import PricingDomain
from apps.payments.models_pricing_rules import PriceDiscount
from apps.payments.pricing.components import component
from apps.payments.pricing.errors import DiscountInvalid

SETTING = ("charges", "pricing.discounts")
FIELDS = ("name", "audience", "plan", "member", "domains", "components", "percent_bps", "amount_off",
          "starts_at", "ends_at", "is_active")


def _authorize(actor, makerspace):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.settings_authority import assert_setting_write
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(makerspace.pk)
    space = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
    return space, assert_setting_write(actor, space, *SETTING)


def _validate(rule):
    unknown = [domain for domain in rule.domains if domain not in PricingDomain.values]
    if unknown:
        raise DiscountInvalid("Unknown pricing areas.", domains=unknown)
    domains = rule.domains or PricingDomain.values
    bad = [key for key in rule.components if not any(component(domain, key) for domain in domains)]
    if bad:
        raise DiscountInvalid("Those components are not in the chosen areas.", components=bad)
    if rule.member_id and not _is_member(rule.makerspace_id, rule.member_id):
        raise DiscountInvalid("A member discount must name a member of this space.")
    try:
        rule.full_clean()
    except DjangoValidationError as exc:
        raise DiscountInvalid(errors=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _is_member(makerspace_id, user_id):
    from apps.makerspaces.models import MakerspaceMembership

    return MakerspaceMembership.objects.filter(makerspace_id=makerspace_id, user_id=user_id, status="active").exists()


def _terms(rule):
    """The rule's terms (no ids): what an audit entry records about it."""
    return {"name": rule.name, "audience": rule.audience, "domains": rule.domains, "components": rule.components,
            "percent_bps": rule.percent_bps, "amount_off": str(rule.amount_off) if rule.amount_off else None,
            "is_active": rule.is_active}


def _apply(rule, data):
    for field in FIELDS:
        if field in data:
            setattr(rule, field, data[field])
    rule.domains = sorted(set(rule.domains or []))
    rule.components = sorted(set(rule.components or []))
    if rule.amount_off is not None:
        rule.amount_off = Decimal(rule.amount_off)
    # A rule is one kind or the other; switching kind clears the old one.
    if "percent_bps" in data and data["percent_bps"] is not None:
        rule.amount_off = None
    if "amount_off" in data and data["amount_off"] is not None:
        rule.percent_bps = None
    if rule.audience != PriceDiscount.Audience.PLAN:
        rule.plan = None
    if rule.audience != PriceDiscount.Audience.MEMBER:
        rule.member = None


@transaction.atomic
def create_discount(actor, makerspace, data):
    space, decision = _authorize(actor, makerspace)
    rule = PriceDiscount(makerspace=space, created_by=actor)
    _apply(rule, data)
    _validate(rule)
    rule.save()
    audit.record(actor, "pricing.discount_created", makerspace=space, target=rule, meta={
        "discount_id": rule.pk, "plan_id": rule.plan_id, "member_id": rule.member_id, "terms": _terms(rule),
        "via": decision.via,
    })
    return rule


@transaction.atomic
def update_discount(actor, rule, data):
    space, decision = _authorize(actor, rule.makerspace)
    rule = PriceDiscount.objects.select_for_update().get(pk=rule.pk)
    if rule.archived_at is not None:
        raise DiscountInvalid("An archived discount cannot change.")
    before = _terms(rule)
    _apply(rule, data)
    _validate(rule)
    rule.save()
    audit.record(actor, "pricing.discount_updated", makerspace=space, target=rule, meta={
        "discount_id": rule.pk, "plan_id": rule.plan_id, "member_id": rule.member_id, "terms": _terms(rule),
        "before": before, "via": decision.via,
    })
    return rule


@transaction.atomic
def archive_discount(actor, rule):
    space, decision = _authorize(actor, rule.makerspace)
    rule = PriceDiscount.objects.select_for_update().get(pk=rule.pk)
    if rule.archived_at is None:
        rule.archived_at, rule.is_active = timezone.now(), False
        rule.save(update_fields=["archived_at", "is_active", "updated_at"])
        audit.record(actor, "pricing.discount_archived", makerspace=space, target=rule, meta={
            "discount_id": rule.pk, "terms": _terms(rule), "via": decision.via,
        })
    return rule
