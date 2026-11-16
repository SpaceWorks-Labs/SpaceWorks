"""Freezing the tax policy onto a charge (`Payment.tax_snapshot`).

The snapshot is taken once, when the charge is raised, and never rewritten: a space
that changes its rate, its GSTIN or its inclusive/exclusive choice must not change what
an existing debt -- or a document already issued for it -- says about tax. With the
`billing.tax` capability off, or the mode `none`, there is no snapshot at all and the
charge is exactly what release 1 raised.
"""

from apps.makerspaces.platform import feature_enabled
from apps.payments.tax.engine import TAXED_SUPPLIES, compute, q

SNAPSHOT_VERSION = 1


def live_settings(makerspace):
    """The space's tax policy when the capability is on and a mode is chosen, else None."""
    if not feature_enabled(makerspace, "billing.tax"):
        return None
    from apps.payments.tax.models_tax import MakerspaceTaxSettings

    policy = MakerspaceTaxSettings.objects.filter(makerspace=makerspace).first()
    if policy is None or policy.mode == MakerspaceTaxSettings.Mode.NONE:
        return None
    return policy


def recipient_identity(makerspace, member):
    """(gstin, state_code) for the payer, read from the membership record when present.

    The membership record fields (`gstin`, `state_code`) belong to lane L4; until it
    merges, an attribute that does not exist yet reads as blank.
    """
    if member is None:
        return "", ""
    from apps.makerspaces.models import MakerspaceMembership
    from apps.payments.tax.gstin import STATE_NAMES, is_valid_gstin, normalize

    membership = MakerspaceMembership.objects.filter(makerspace=makerspace, user=member).first()
    gstin = normalize(getattr(membership, "gstin", "") or "")
    state = str(getattr(membership, "state_code", "") or "").strip().zfill(2) if membership else ""
    gstin = gstin if is_valid_gstin(gstin) else ""
    if gstin:
        state = gstin[:2]
    return gstin, state if state in STATE_NAMES else ""


def build_snapshot(makerspace, *, currency, member=None):
    policy = live_settings(makerspace)
    if policy is None:
        return None
    gstin, recipient_state = recipient_identity(makerspace, member)
    return snapshot_for(policy, currency=currency, recipient_gstin=gstin, recipient_state=recipient_state)


def snapshot_for(policy, *, currency, recipient_gstin="", recipient_state=""):
    """The snapshot a charge would freeze under `policy` (saved, or an unsaved preview)."""
    currency = (currency or "").lower()
    base = {"version": SNAPSHOT_VERSION, "mode": policy.mode, "rate_bps": policy.rate_bps,
            "inclusive": policy.prices_include_tax, "currency": currency}
    if policy.mode == policy.Mode.SINGLE:
        return {**base, "tax_name": policy.tax_name.strip(), "supply_type": "single"}
    place = recipient_state or policy.state_code
    if policy.scheme == policy.Scheme.COMPOSITION:
        supply = "composition"
    elif policy.exempt:
        supply = "exempt"
    elif currency != "inr":
        supply = policy.foreign_currency
    else:
        supply = "intra" if place == policy.state_code else "inter"
    return {**base, "tax_name": "GST", "supply_type": supply, "sac_code": policy.sac_code,
            "scheme": policy.scheme, "supplier_gstin": policy.gstin, "supplier_state": policy.state_code,
            "recipient_gstin": recipient_gstin, "recipient_state": recipient_state, "place_of_supply": place,
            "lut_number": policy.lut_number if supply == "export_lut" else ""}


def freeze_for_charge(makerspace, amount, currency, member=None):
    """(amount to charge, snapshot or None) for a charge being raised now.

    An exclusive policy adds the tax on top of the price the domain computed; an
    inclusive one charges the price as entered. The split is frozen alongside.
    """
    from apps.payments.tax.apportion import figures_json

    snapshot = build_snapshot(makerspace, currency=currency, member=member)
    if snapshot is None:
        return amount, None
    currency = (currency or "").lower()
    split = compute(amount, snapshot, currency, entered=True)
    snapshot["entered_amount"] = str(q(amount, currency))
    snapshot["figures"] = figures_json(split)
    return split.gross, snapshot


def is_taxed(snapshot):
    return bool(snapshot) and snapshot.get("supply_type") in TAXED_SUPPLIES
