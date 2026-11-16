"""A8 at the submit boundary: refuse a submit whose shown price has since moved.

A member's client sends back the `digest` of the price preview it showed (body field
`quote_digest`). When present and the current quote differs, the submit is refused with
409 `price_changed` carrying the new quote, before anything is written. Absent (an older
client, staff tools), nothing changes. Never charge more than was shown.
"""

from apps.makerspaces.platform import feature_enabled
from apps.payments.pricing.rates import PRICING_FEATURE


def check_submitted_digest(request, makerspace, domain, target, params, member=None):
    digest = request.data.get("quote_digest") if hasattr(request.data, "get") else None
    if not digest or not feature_enabled(makerspace, PRICING_FEATURE):
        return None
    from apps.payments.pricing import quote, verify_digest

    viewer = member if member is not None else getattr(request, "user", None)
    viewer = viewer if getattr(viewer, "is_authenticated", False) else None
    from apps.payments.pricing.discounts import member_plan_ids
    if viewer is not None and member_plan_ids(makerspace, viewer) is None:
        viewer = None
    priced = quote(makerspace, domain, target, member=viewer, params=params)
    if domain == "loans":
        priced = priced.subset(*{line.subject_type for line in priced.lines if line.subject_type != "loan_deposit"})
    return verify_digest(priced, str(digest))
