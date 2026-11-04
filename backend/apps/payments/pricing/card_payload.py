"""The rate-card payload the pricing screen reads (lane L15)."""

from apps.payments.models_pricing import PricingDomain
from apps.payments.pricing.adapters import LOAN_LEGACY_COMPONENTS, loan_legacy_values
from apps.payments.pricing.components import SETTINGS_MODULES, components


def _decision(actor, makerspace, module, key):
    from apps.makerspaces.settings_authority import decide

    if module is None:
        return None
    return decide(actor, makerspace, module, key)


def card_payload(card, actor):
    domain = card.domain
    module = SETTINGS_MODULES.get(domain)
    decision = _decision(actor, card.makerspace, module, f"pricing.{domain}")
    timing = _decision(actor, card.makerspace, "inventory", "rental_timing") if domain == "loans" else None
    lines = []
    for spec in components(domain):
        if domain == "loans" and spec.key in LOAN_LEGACY_COMPONENTS:
            continue
        stored = card.lines.get(spec.key)
        rate = card.default(spec.key)
        lines.append({
            "component": spec.key, "label": spec.label, "unit": spec.unit, "has_cap": spec.has_cap,
            "has_grace": spec.has_grace, "has_increment": spec.has_increment, "has_minimum": spec.has_minimum,
            "discountable": spec.discountable, "staff_set": spec.staff_set, "prefill_only": spec.prefill_only,
            "read_only": spec.read_only,
            "amount": stored.amount if stored else rate.amount,
            "cap": stored.cap if stored else rate.cap,
            "grace_units": stored.grace_units if stored else rate.grace,
            "billing_increment": stored.billing_increment if stored else rate.increment,
            "minimum": stored.minimum if stored else rate.minimum,
            "source": "default" if stored else ("legacy" if rate.amount > 0 else "none"),
        })
    return {
        "domain": domain, "label": PricingDomain(domain).label, "enabled": card.enabled,
        "currency": card.currency, "mode": card.mode, "stored": card.row is not None,
        "editable": bool(decision and decision.allowed), "via": decision.via if decision else None,
        "locked": bool(decision and decision.locked), "refusal": decision.code if decision and not decision.allowed else None,
        "rental_timing": card.rental_timing if domain == "loans" else None,
        "rental_timing_editable": bool(timing and timing.allowed),
        "failed_job_charge": card.failed_job_charge if domain == "machines" else None,
        "lines": lines,
        "lending": loan_legacy_values(card.payment_settings) if domain == "loans" else None,
    }
