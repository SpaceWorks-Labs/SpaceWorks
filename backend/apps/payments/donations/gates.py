"""Switches and authority for donations and sponsors (#95: off means 404, data kept).

Staff surfaces are the finance ledger's `donations` domain (#100): only holders of
`view_finance` (the Space Manager and finance staff) read them, and recording, cancelling
or opening a refund case also needs `record_payment`.
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled

DONATIONS, PLEDGES, SPONSORS, TAX = (
    "finance.donations", "finance.recurring_donations", "finance.sponsors", "finance.tax_exempt_receipts")


class FeatureOff(NotFound):
    def __init__(self, key):
        super().__init__({"detail": "This feature is turned off here.", "code": "feature_disabled", "key": key})


def require_feature(space, key):
    if not feature_enabled(space, key):
        raise FeatureOff(key)
    return space


def public_space(slug, key=DONATIONS):
    from apps.makerspaces.lookup import get_public_makerspace

    return require_feature(get_public_makerspace(slug), key)


def staff_space(actor, makerspace_id, key, *, record=False):
    """The servable space when `actor` holds finance authority there, else 404."""
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    space = servable_queryset(Makerspace.objects.filter(pk=makerspace_id)).first()
    if space is None or not rbac.can(actor, rbac.Action.VIEW_FINANCE, makerspace_id):
        raise NotFound("Makerspace not found.")
    require_feature(space, key)
    if record and not rbac.can(actor, rbac.Action.RECORD_PAYMENT, makerspace_id):
        raise PermissionDenied({"detail": "Recording money needs record_payment.", "code": "record_payment_required"})
    return space


def scoped(actor, model, makerspace_id):
    """Every staff list goes through the Auth module's makerspace scoping."""
    return rbac.scope_by_action(actor, rbac.Action.VIEW_FINANCE, model.objects.filter(makerspace_id=makerspace_id),
                                field="makerspace_id")
