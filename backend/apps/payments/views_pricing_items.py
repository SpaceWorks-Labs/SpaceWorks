"""Per-item prices: the PriceOverrideCard read and its inherit / free / custom writes.

Lane L15 (A9, A13). Per-item prices belong to whoever already edits the item: inventory
items to `edit_inventory`, machines and material pools to `manage_machines` inside the
caller's machine scope, rooms to `manage_bookings`. Finance staff may read. An item's own
price field (a room's price, an item's deposit) is its custom price; Free keeps it free
under a paid default; Inherit follows the space default.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.openapi_errors import errors
from apps.payments.models_pricing import PriceOverride
from apps.payments.pricing import admin_services
from apps.payments.pricing import targets as registry
from apps.payments.pricing.components import components
from apps.payments.pricing.http import ITEM_ACTIONS, require_domain, require_pricing, space_for
from apps.payments.pricing.rates import RateCard
from apps.payments.pricing.serializers_rules import PriceOverrideCardSerializer, PriceOverrideWriteSerializer

TAGS = ["Pricing"]


def _legacy(target_type, target):
    if target_type == PriceOverride.TargetType.INVENTORY_PRODUCT:
        return {"deposit": target.deposit_amount}
    if target_type == PriceOverride.TargetType.BOOKABLE_SPACE:
        return {"per_booking": target.payment_amount}
    return {}


def _middle(card, target_type, target):
    from apps.payments.pricing.build_machines import _type_rates

    if target_type == PriceOverride.TargetType.MACHINE:
        return _type_rates(card, target.machine_type)
    if target_type == PriceOverride.TargetType.CONSUMABLE_POOL and target.machine_id:
        return {key: rate for key, rate in _type_rates(card, target.machine.machine_type).items() if key == "material"}
    return {}


def card(actor, space, target_type, target):
    domain = registry.DOMAINS[target_type]
    rates = RateCard(space, domain)
    legacy, middle = _legacy(target_type, target), _middle(rates, target_type, target)
    rows = []
    for spec in components(domain):
        if target_type not in spec.targets:
            continue
        row = rates.override(spec.key, target_type, target.pk)
        effective = rates.resolve(spec.key, ((target_type, target.pk),), legacy_item=legacy.get(spec.key),
                                  middle=middle.get(spec.key))
        mode = row.mode if row else ("custom" if effective.source == "item" else "inherit")
        rows.append({"component": spec.key, "label": spec.label, "unit": spec.unit, "has_cap": spec.has_cap,
                     "mode": mode, "amount": row.amount if row else (effective.amount if mode == "custom" else None),
                     "cap": row.cap if row else None, "effective_amount": effective.amount,
                     "effective_source": effective.source, "default_amount": rates.default(spec.key).amount})
    return {"target_type": target_type, "target_id": target.pk, "label": getattr(target, "name", str(target.pk)),
            "domain": domain, "currency": rates.currency, "enabled": rates.enabled,
            "editable": registry.can_price(actor, target_type, target), "components": rows}


def _resolve(request, makerspace_id, target_type, target_id):
    if target_type not in registry.MODELS:
        raise NotFound("Unknown item type.")
    space = space_for(request.user, makerspace_id, *ITEM_ACTIONS)
    require_pricing(space)
    require_domain(space, registry.DOMAINS[target_type])
    target = registry.load(target_type, target_id, space.pk)
    if target is None or not registry.can_view(request.user, target_type, target):
        raise NotFound("Item not found.")
    return space, target


PARAMS = [OpenApiParameter("target_type", str, OpenApiParameter.PATH, enum=PriceOverride.TargetType.values)]


class PriceOverrideView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read an item's prices: effective price and its source per component",
                   parameters=PARAMS, responses={200: PriceOverrideCardSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, target_type, target_id):
        space, target = _resolve(request, makerspace_id, target_type, target_id)
        return Response(PriceOverrideCardSerializer(card(request.user, space, target_type, target)).data)

    @extend_schema(tags=TAGS, summary="Set one component of an item's price to inherit, free or custom",
                   description="Only staff who edit the item (403 otherwise). A custom deposit or room price "
                               "is written to the item's own price field. Audited `pricing.override_set` / "
                               "`pricing.override_cleared`. 400 `component_not_allowed` for a component this "
                               "item type does not take.",
                   parameters=PARAMS, request=PriceOverrideWriteSerializer,
                   responses={200: PriceOverrideCardSerializer, **errors(400, 401, 403, 404, 423)})
    def put(self, request, makerspace_id, target_type, target_id):
        space, target = _resolve(request, makerspace_id, target_type, target_id)
        body = PriceOverrideWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        admin_services.set_override(request.user, space, target_type, target.pk, data["component"],
                                    mode=data["mode"], amount=data.get("amount"), cap=data.get("cap"))
        target.refresh_from_db()
        return Response(PriceOverrideCardSerializer(card(request.user, space, target_type, target)).data)
