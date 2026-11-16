"""Hack-money G13: a Space Manager chooses the payee country/method pairs the space accepts.

The deployment keeps the ceiling. A host with an operator policy in `EVENT_PAYOUT_TENANT_POLICIES`
is capped by that policy; any other host is capped by `EVENT_PAYOUT_TEMPLATE_CEILING` (a list of
[country, method] pairs; unset means every supported pair). An empty space selection changes
nothing, so existing deployments behave exactly as before. A member's input never reaches here.
"""
from .templates import COUNTRIES, TEMPLATE_VERSION, template_key
from .validation import PayoutValidationError

METHODS = ("bank_transfer", "upi", "paypal", "wise", "cash", "cheque", "other")


def supported_pairs():
    pairs = []
    for country in sorted(COUNTRIES):
        for method in METHODS:
            try:
                pairs.append((country, method, template_key(country, method), TEMPLATE_VERSION))
            except PayoutValidationError:
                continue
    return pairs


def deployment_ceiling():
    from django.conf import settings
    allowed = getattr(settings, "EVENT_PAYOUT_TEMPLATE_CEILING", None)
    pairs = supported_pairs()
    if allowed is None:
        return frozenset(pairs)
    wanted = {tuple(item) for item in allowed}
    return frozenset(row for row in pairs if row[:2] in wanted)


def space_selection(makerspace_id):
    from apps.payments.models import EventMoneySettings
    row = EventMoneySettings.objects.filter(makerspace_id=makerspace_id).values_list("payee_templates", flat=True).first()
    return {tuple(item) for item in (row or ()) if isinstance(item, (list, tuple)) and len(item) == 2}


def narrow(makerspace_id, operator_enabled, operator_documents, has_operator_policy):
    chosen = space_selection(makerspace_id)
    if not chosen:
        return frozenset(operator_enabled), frozenset(operator_documents)
    ceiling = operator_enabled if has_operator_policy else deployment_ceiling()
    picked = frozenset(row for row in ceiling if row[:2] in chosen)
    return picked, frozenset(item for item in operator_documents if any(row[:2] == item for row in picked))


def validate_selection(pairs, makerspace_id):
    """A Space Manager's selection: known pairs inside this host's ceiling, no duplicates."""
    from django.conf import settings
    policy = getattr(settings, "EVENT_PAYOUT_TENANT_POLICIES", {}).get(str(makerspace_id))
    if policy:
        from .templates import operator_templates
        ceiling = operator_templates(makerspace_id)[0]
    else:
        ceiling = deployment_ceiling()
    allowed = {row[:2] for row in ceiling}
    cleaned = []
    for item in pairs:
        pair = tuple(item) if isinstance(item, (list, tuple)) else ()
        if len(pair) != 2 or pair not in allowed or list(pair) in cleaned:
            raise PayoutValidationError("payee_template_unsupported")
        cleaned.append(list(pair))
    return sorted(cleaned)
