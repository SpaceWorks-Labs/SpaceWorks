"""Native makerspace selection for a caller's OWN charges without a membership there.

A native member grant normally selects a makerspace through its active community
membership. An account-only borrower owes a loan deposit or late fee in a space where they
hold no membership; the web reaches those charges through `member_may_see_own_charges` and
`member_payment_queryset`, so the phone must too, or the same person can pay on the web but
not in the app (decision 354).

The exception is narrow on purpose: only the member payment routes below, only for a
member (never staff or event) grant, only when the caller holds no ACTIVE membership in the
space and `member_may_see_own_charges` admits them (it still refuses a REVOKED member, bar
their own rejoin admission charge, exactly as on the web). The selection then carries no membership, so every other
membership-dependent native route (`require_native_selected_makerspace`) still refuses.
Each listed view re-applies its own ownership checks exactly as on the web.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

OWN_CHARGE_ROUTES = frozenset({
    "member-my-usage",
    "member-payment-history",
    "member-payment-checkout",
    "member-payment-mobile-intent",
    "member-paid-claim",
    "member-refund-request",
    "member-refund-withdraw",
    "member-payment-documents",
    "member-payment-document-url",
})


def admits_own_charge_selection(request, user, makerspace_id):
    """Whether a membership-less member grant may select ``makerspace_id`` for this route."""
    name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    if name not in OWN_CHARGE_ROUTES:
        return False
    from apps.payments.member_access import member_may_see_own_charges

    return member_may_see_own_charges(user, makerspace_id)


def require_native_charge_selection(request, makerspace_id):
    """The native selection a payment route needs: the path's space, by membership or charge."""
    if getattr(request, "selected_makerspace_id", None) != makerspace_id or not (
        getattr(request, "selected_makerspace_membership", None) is not None
        or getattr(request, "selected_makerspace_own_charges", False)
    ):
        raise PermissionDenied(gettext("A matching native makerspace selection is required."))
