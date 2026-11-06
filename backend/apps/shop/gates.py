"""The shop's switches and staff scoping, checked at every boundary (#95, LANE-RULES §9).

With the `shop` module off every shop route answers 404 `shop_closed`, and with a feature
off its routes answer 404 `feature_off`; data is kept. Staff spaces resolve through rbac
(`scope_by_action`), so a person without the action in that space gets a 404, never a hint.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled

from .errors import ShopRefused

MANAGE, SELL, VIEW = rbac.Action.MANAGE_SHOP, rbac.Action.SELL_SHOP, rbac.Action.VIEW_SHOP


def is_on(space, key=None):
    return module_enabled(space, "shop") and (key is None or feature_enabled(space, key))


def require_shop(space):
    if not module_enabled(space, "shop"):
        raise ShopRefused("shop_closed", "This space does not run a shop.")
    return space


def require_feature(space, key):
    require_shop(space)
    if not feature_enabled(space, key):
        raise ShopRefused("feature_off", "This shop feature is switched off.", feature=key)
    return space


def public_space(slug):
    """The space behind a public shop URL, when its online shop is open."""
    from apps.makerspaces.editions import require_public_surface
    from apps.makerspaces.lookup import get_public_makerspace

    space = get_public_makerspace(slug)
    require_public_surface("shop")
    if not getattr(space, "public_site_enabled", True):
        raise ShopRefused("shop_closed", "This space does not run a shop.")
    return require_feature(space, "shop.online")


def staff_space(actor, makerspace_id, action=VIEW):
    """The makerspace `actor` holds `action` in, with the shop on; 404 otherwise."""
    from apps.makerspaces.models import Makerspace

    space = rbac.scope_by_action(actor, action, Makerspace.objects.all(), field="pk").filter(
        pk=makerspace_id).first()
    if space is None:
        raise NotFound(gettext("Makerspace not found."))
    return require_shop(space)


def write_allowed(space):
    """Refuse writes while this space is frozen for a move (the tenant-migration source gate)."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(getattr(space, "pk", space))
    return space


def require_charges(space):
    """Every sale is recorded (#94): with shop charge tracking off the shop cannot sell."""
    from apps.payments.availability import charge_tracking_enabled

    if not charge_tracking_enabled(space, "shop"):
        raise ShopRefused("charges_off", "Shop sales are not being recorded here; turn on shop charges first.")
    return space


def online_rail(space):
    from apps.payments.availability import online_payments_enabled

    return online_payments_enabled(space, "shop")
