"""Shared lookups for the pricing endpoints: the space, the domain gate, the switches.

Every staff pricing route resolves its makerspace through rbac (a space the caller holds
none of the named actions in is 404, never 403), refuses a domain whose module is off
(`pricing_domain_unknown`) and refuses everything while `charges.pricing` is off
(`pricing_disabled`) -- a switched-off feature leaves no API surface (#95).
"""

from django.shortcuts import get_object_or_404

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.payments.pricing.components import DOMAIN_MODULES, SETTINGS_MODULES, domain_known
from apps.payments.pricing.errors import PricingDisabled, PricingDomainUnknown
from apps.payments.pricing.rates import PRICING_FEATURE


def space_for(actor, makerspace_id, *actions, lock=False):
    scope = rbac.makerspaces_for_actions(actor, *actions)
    spaces = servable_queryset()
    if scope is not rbac.ALL:
        spaces = spaces.filter(pk__in=scope)
    if lock:
        spaces = spaces.select_for_update()
    return get_object_or_404(spaces, pk=makerspace_id)


def require_pricing(makerspace):
    if not feature_enabled(makerspace, PRICING_FEATURE):
        raise PricingDisabled()


def require_domain(makerspace, domain):
    if not domain_known(domain) or not module_enabled(makerspace, DOMAIN_MODULES[domain]):
        raise PricingDomainUnknown(domain)


def domain_read_actions(domain):
    """Who may READ a domain's rate card: the SM, the domain's manager, or finance."""
    from apps.makerspaces.settings_authority_registry import MODULE_MANAGER_ACTIONS

    actions = [rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE]
    module = SETTINGS_MODULES.get(domain)
    if module in MODULE_MANAGER_ACTIONS:
        actions.append(MODULE_MANAGER_ACTIONS[module])
    if domain == "membership":
        actions.append(rbac.Action.MANAGE_MEMBERS)
    return actions


#: Any staff action that edits or reads a priced item; the per-item checks narrow further.
ITEM_ACTIONS = (rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_MACHINES, rbac.Action.MANAGE_BOOKINGS,
                rbac.Action.VIEW_FINANCE, rbac.Action.MANAGE_MAKERSPACE)
