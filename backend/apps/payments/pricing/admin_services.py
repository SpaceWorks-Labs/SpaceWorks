"""Staff writes for the rate card, rental timing and per-item overrides (lane L15, A9/A13).

Every function is atomic, audited, refuses during a tenant move (`assert_write_allowed`)
and writes settings through L17's authority layer (#101):

* a domain's defaults (`pricing.<domain>`): the Space Manager, or that module's manager
  holding its settings grant; an SM lock refuses (`setting_locked`). Audited as
  `settings.changed` with the authority used.
* rental timing: the Space Manager, or the Inventory Manager WITHOUT a grant (#128
  C-11d, L17's fixed exception); an SM lock still refuses. Applies to loans issued after.
* an item override: whoever already edits the item (`targets.can_price`). Audited as
  `pricing.override_set` / `pricing.override_cleared`.

Discounts live in `discount_services.py`.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit import services as audit
from apps.payments.models_pricing import PriceOverride, PricingDefault, PricingDefaultLine
from apps.payments.pricing import components as registry
from apps.payments.pricing import targets as target_registry
from apps.payments.pricing.adapters import LOAN_LEGACY_COMPONENTS, write_loan_legacy
from apps.payments.pricing.errors import ComponentNotAllowed, PricingDomainUnknown

LINE_FIELDS = ("amount", "cap", "grace_units", "billing_increment", "minimum")


def _lock_space(makerspace):
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(makerspace.pk)
    return Makerspace.objects.select_for_update().get(pk=makerspace.pk)


def setting_key(domain):
    return f"pricing.{domain}"


def _summary(row):
    if row is None:
        return None
    return {"mode": row.mode, "rental_timing": row.rental_timing, "failed_job_charge": row.failed_job_charge,
            "lines": {line.component: {field: str(getattr(line, field)) for field in LINE_FIELDS}
                      for line in row.lines.all()}}


@transaction.atomic
def set_default(actor, makerspace, domain, *, mode=None, lines=(), loan_block=None, failed_job_charge=None):
    from apps.makerspaces.settings_authority import assert_setting_write, record_change

    module = registry.SETTINGS_MODULES.get(domain)
    if module is None:
        raise PricingDomainUnknown(domain)
    space = _lock_space(makerspace)
    decision = assert_setting_write(actor, space, module, setting_key(domain))
    row, _ = PricingDefault.objects.select_for_update().get_or_create(
        makerspace=space, domain=domain,
        defaults={"rental_timing": PricingDefault.RentalTiming.AT_CHECKOUT if domain == "loans" else ""})
    before = {**_summary(row)}
    legacy_before, legacy_after = {}, {}
    if mode is not None:
        row.mode = mode
    if failed_job_charge is not None:
        if domain != "machines":
            raise ComponentNotAllowed("Failed-job charging applies to machines only.")
        row.failed_job_charge = failed_job_charge
    row.updated_by = actor
    row.save()
    for entry in lines:
        spec = registry.component(domain, entry["component"])
        if spec is None or spec.read_only:
            raise ComponentNotAllowed(component=entry["component"])
        if domain == "loans" and spec.key in LOAN_LEGACY_COMPONENTS:
            raise ComponentNotAllowed("Set the deposit and late fee in the deposit and late fee section.", component=spec.key)
        values = {field: entry[field] for field in LINE_FIELDS if field in entry}
        if not spec.has_cap:
            values["cap"] = None
        PricingDefaultLine.objects.update_or_create(default=row, component=spec.key, defaults=values)
    if loan_block:
        if domain != "loans":
            raise ComponentNotAllowed("The deposit and late fee section applies to Inventory loans only.")
        legacy_before, legacy_after = write_loan_legacy(space, loan_block)
    after = _summary(row)
    if legacy_after:
        before["lending"], after["lending"] = legacy_before, legacy_after
    record_change(actor, space, module, setting_key(domain), before, after, decision)
    from apps.payments.price_drop.triggers import after_domain_change
    after_domain_change(actor, space, domain, row)  # lane L24: a lowered rate opens refund cases
    return row


@transaction.atomic
def set_rental_timing(actor, makerspace, timing):
    from apps.makerspaces.settings_authority import assert_setting_write, record_change

    space = _lock_space(makerspace)
    decision = assert_setting_write(actor, space, "inventory", "rental_timing")
    row, _ = PricingDefault.objects.select_for_update().get_or_create(
        makerspace=space, domain="loans", defaults={"rental_timing": PricingDefault.RentalTiming.AT_CHECKOUT})
    before = row.rental_timing or PricingDefault.RentalTiming.AT_CHECKOUT
    row.rental_timing = timing
    row.updated_by = actor
    row.save(update_fields=["rental_timing", "updated_by", "updated_at"])
    record_change(actor, space, "inventory", "rental_timing", before, timing, decision)
    return row


def _target(actor, makerspace, target_type, target_id):
    target = target_registry.load(target_type, target_id, makerspace.pk)
    if target is None or not target_registry.can_view(actor, target_type, target):
        raise NotFound("Item not found.")
    return target


@transaction.atomic
def set_override(actor, makerspace, target_type, target_id, component, *, mode, amount=None, cap=None):
    space = _lock_space(makerspace)
    target = _target(actor, space, target_type, target_id)
    if not target_registry.can_price(actor, target_type, target):
        raise PermissionDenied("Only staff who edit this item may change its price.")
    domain = target_registry.DOMAINS[target_type]
    spec = registry.component(domain, component)
    if spec is None or target_type not in spec.targets:
        raise ComponentNotAllowed(component=component)
    field = PriceOverride.FIELDS[target_type]
    existing = PriceOverride.objects.select_for_update().filter(
        makerspace=space, component=component, target_type=target_type, **{field: target}).first()
    before = {"mode": existing.mode, "amount": str(existing.amount), "cap": str(existing.cap)} if existing else None
    legacy = _legacy_field(target_type, component)
    if mode == PriceOverride.Mode.CUSTOM and legacy:
        # The item's own price field IS its custom price: write it there, so the item's
        # form and its price card can never disagree (no row needed).
        _write_legacy(target, legacy, Decimal(amount))
        if existing:
            existing.delete()
        row = None
    elif mode == PriceOverride.Mode.INHERIT:
        if legacy:
            _write_legacy(target, legacy, None)
        if existing:
            existing.delete()
        row = None
    else:
        if legacy:
            _write_legacy(target, legacy, None)
        row = existing or PriceOverride(makerspace=space, domain=domain, component=component,
                                        target_type=target_type, **{field: target})
        row.mode = mode
        row.amount = Decimal(amount) if mode == PriceOverride.Mode.CUSTOM else None
        row.cap = Decimal(cap) if cap is not None and spec.has_cap else None
        row.updated_by = actor
        row.full_clean()
        row.save()
    _audit_override(actor, space, target, domain, component, target_type, mode, amount, cap, before)
    from apps.payments.price_drop.triggers import after_override
    after_override(actor, space, target_type, target)  # lane L24: a lowered price opens refund cases
    return row


def _audit_override(actor, space, target, domain, component, target_type, mode, amount, cap, before):
    if mode == PriceOverride.Mode.INHERIT:
        audit.record(actor, "pricing.override_cleared", makerspace=space, target=target, meta={
            "domain": domain, "component": component, "target_type": target_type, "target_id": target.pk,
            "before": before,
        })
        return
    audit.record(actor, "pricing.override_set", makerspace=space, target=target, meta={
        "domain": domain, "component": component, "target_type": target_type, "target_id": target.pk,
        "mode": mode, "amount": None if amount is None else str(amount), "cap": None if cap is None else str(cap),
        "before": before,
    })


@transaction.atomic
def set_currency(actor, makerspace, currency):
    """The currency new charges are raised in: a finance setting, Space Manager only."""
    from apps.makerspaces.settings_authority import assert_setting_write, record_change
    from apps.payments.models import MakerspacePaymentSettings

    space = _lock_space(makerspace)
    decision = assert_setting_write(actor, space, "payments", "default_currency")
    settings_row, _ = MakerspacePaymentSettings.objects.select_for_update().get_or_create(makerspace=space)
    before, after = settings_row.default_currency, currency.strip().lower()
    if before != after:
        settings_row.default_currency = after
        settings_row.save()
        record_change(actor, space, "payments", "default_currency", before, after, decision)
    return after


LEGACY_FIELDS = {
    (PriceOverride.TargetType.INVENTORY_PRODUCT, "deposit"): "deposit_amount",
    (PriceOverride.TargetType.BOOKABLE_SPACE, "per_booking"): "payment_amount",
}


def _legacy_field(target_type, component):
    return LEGACY_FIELDS.get((target_type, component))


def _write_legacy(target, field, amount):
    nullable = type(target)._meta.get_field(field).null
    value = amount if amount is not None else (None if nullable else Decimal("0"))
    if getattr(target, field) != value:
        setattr(target, field, value)
        names = {item.name for item in type(target)._meta.concrete_fields}
        target.save(update_fields=[field, *(["updated_at"] if "updated_at" in names else [])])
