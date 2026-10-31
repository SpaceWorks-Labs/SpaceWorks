"""The sample invoice the tax settings screen shows while staff edit (computes only)."""

from apps.makerspaces.local_time import local_now
from apps.payments.numbering_fy import format_number
from apps.payments.tax.document_tax import notes, title
from apps.payments.tax.engine import compute, q
from apps.payments.tax.fy import fy_start
from apps.payments.tax.snapshot import snapshot_for


def preview(space, saved, data):
    policy = saved
    if data.get("settings"):
        policy = type(saved)(makerspace=space, **{
            field.name: getattr(saved, field.name) for field in saved._meta.concrete_fields
            if field.name not in ("id", "makerspace", "updated_by", "updated_at")})
        for key, value in data["settings"].items():
            setattr(policy, key, value)
        policy.full_clean(exclude=["makerspace"])
    currency = (data.get("currency") or "inr").lower()
    amount = data["amount"]
    if policy.mode == policy.Mode.NONE:
        value = q(amount, currency)
        return {"title": "Receipt", "currency": currency, "entered_amount": value, "taxable": value,
                "tax": q(0, currency), "gross": value, "supply_type": "none", "place_of_supply": "",
                "components": [], "notes": ["No tax is charged."], "sample_number": "000001"}
    snapshot = snapshot_for(policy, currency=currency, recipient_state=data.get("recipient_state") or "")
    split = compute(amount, snapshot, currency, entered=True)
    start = fy_start(space, local_now(space).date())
    return {"title": title(snapshot, "receipt"), "currency": currency, "entered_amount": q(amount, currency),
            "taxable": split.taxable, "tax": split.tax, "gross": split.gross,
            "supply_type": snapshot["supply_type"], "place_of_supply": snapshot.get("place_of_supply", ""),
            "components": [component.as_json() for component in split.components], "notes": notes(snapshot),
            "sample_number": format_number(policy.invoice_prefix or "INV", start, 1)}
