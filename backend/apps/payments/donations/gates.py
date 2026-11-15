"""Switches and authority for donations and sponsors (#95: off means 404, data kept).

Staff surfaces are the finance ledger's `donations` domain (#100): holders of `view_finance`
(the Space Manager and finance staff) or `manage_donations` (the Fundraising role, decision
242(m); the Space Manager holds it through `manage_makerspace`) read them. Recording,
cancelling or opening a refund case needs `manage_donations` or `record_payment`. No area
manager holds either, so donation money never reaches an area's views.
"""

from contextlib import contextmanager

from django.utils.translation import gettext
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled

DONATIONS, PLEDGES, SPONSORS, TAX = (
    "finance.donations", "finance.recurring_donations", "finance.sponsors", "finance.tax_exempt_receipts")


class DonationRefused(APIException):
    """A typed 400 the screens read: `{"detail", "code", "field"}` (like the refund refusals)."""

    status_code = 400

    def __init__(self, detail, code, field=None):
        self.detail = {"detail": detail, "code": code, **({"field": field} if field else {})}


class FeatureOff(NotFound):
    def __init__(self, key):
        super().__init__({"detail": gettext("This feature is turned off here."), "code": "feature_disabled", "key": key})


def tax_key(space, tax):
    """Prepare the tenant key OUTSIDE any transaction when an 80G identity will be written."""
    from contextlib import nullcontext

    if not tax or not tax[0]:
        return nullcontext()
    from apps.encryption.tenant_preparation import holds_tenant_key, prepare_tenant_key, tenant_key_context

    if holds_tenant_key(space.pk):
        return nullcontext()
    return tenant_key_context(prepare_tenant_key(space.pk))


def require_tracking(space):
    """#184 G10: gifts and sponsor money are recorded only while `charges.enabled` and
    `charges.donations` are on. Off, the space takes no donation or sponsor money at all."""
    from apps.payments.availability import charge_tracking_enabled

    if not charge_tracking_enabled(space, "donations"):
        raise DonationRefused(gettext("This space is not recording donation or sponsor money right now."), "charges_off")
    return space


def require_feature(space, key):
    if not feature_enabled(space, key):
        raise FeatureOff(key)
    return space


def public_space(slug, key=DONATIONS):
    from apps.makerspaces.lookup import get_public_makerspace

    return require_feature(get_public_makerspace(slug), key)


def read_action(actor, makerspace_id):
    """The action that admits `actor` to this space's donations, or None."""
    for action in (rbac.Action.MANAGE_DONATIONS, rbac.Action.VIEW_FINANCE):
        if rbac.can(actor, action, makerspace_id):
            return action
    return None


def may_record(actor, makerspace_id):
    return any(rbac.can(actor, action, makerspace_id)
               for action in (rbac.Action.MANAGE_DONATIONS, rbac.Action.RECORD_PAYMENT))


def require_fundraising_locked(space, key=DONATIONS, *, money=False, tax=None, tax_request=None, features=()):
    """One fresh switch fence, inside an atomic block, before any side effect.

    Lock order is makerspace before donor/pledge/payment. `key=None` only locks:
    core settlement must finish even with fundraising off; optional receipt/rail
    work then uses this fresh row to decide whether to skip its own effects.
    Tax admission applies to NEW details, never a period reusing stored details.
    """
    from apps.makerspaces.guards import feature_off, require_feature_locked
    from apps.makerspaces.models import Makerspace

    if key is None:
        space = Makerspace.objects.select_for_update(no_key=True).get(pk=getattr(space, "pk", space))
    else:
        space = require_feature_locked(space, DONATIONS)
        if not feature_enabled(space, key):
            raise feature_off(key)
    for feature in features:
        if not feature_enabled(space, feature):
            raise feature_off(feature)
    if money:
        require_tracking(space)
    if tax_request is not None or (tax and tax[0]):
        from .tax_receipts import clean_request

        clean_request(space, tax_request if tax_request is not None else {
            "wants_tax_receipt": tax[0], "donor_pan": tax[1], "donor_address": tax[2]})
    return space


@contextmanager
def donation_write(makerspace_id, key=DONATIONS, **requirements):
    """Serialize fundraising writes against the Space Manager's switch changes."""
    from apps.tenant_migration.gate_runtime import tenant_write

    with tenant_write(makerspace_id):
        yield require_fundraising_locked(makerspace_id, key, **requirements)


def staff_space(actor, makerspace_id, key, *, record=False):
    """Standing before switches: foreign space 404, local missing action 403."""
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    visible = rbac.scope_by_visibility_or_action(
        actor, rbac.Action.MANAGE_DONATIONS, Makerspace.objects.filter(pk=makerspace_id), field="pk")
    space = servable_queryset(visible).first()
    if space is None:
        raise NotFound(gettext("Makerspace not found."))
    if read_action(actor, makerspace_id) is None:
        raise PermissionDenied()
    require_feature(space, key)
    if record and not may_record(actor, makerspace_id):
        raise PermissionDenied({"detail": gettext("Recording money needs manage_donations or record_payment."),
                                "code": "record_payment_required"})
    return space


def scoped(actor, model, makerspace_id):
    """Every staff list goes through the Auth module's makerspace scoping."""
    action = read_action(actor, makerspace_id) or rbac.Action.VIEW_FINANCE
    return rbac.scope_by_action(actor, action, model.objects.filter(makerspace_id=makerspace_id),
                                field="makerspace_id")
