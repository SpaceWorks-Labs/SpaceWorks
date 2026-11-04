"""Staff rate cards: a domain's defaults, the impact preview, rental timing, the currency.

Lane L15 (#84/#85, A1/A9/A13). Reads: the Space Manager, the domain's manager, or
finance staff. Writes go through L17's settings authority: the Space Manager, or the
module manager holding the module's settings grant (`setting_not_delegated` /
`setting_locked` otherwise). Rental timing is the Inventory Manager's too, without a
grant (#128 C-11d). The currency is a finance setting: Space Manager only. Everything
is 404 while `charges.pricing` is off.
"""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.openapi_errors import errors
from apps.payments.pricing import admin_services
from apps.payments.pricing.card_payload import card_payload
from apps.payments.pricing.components import SETTINGS_MODULES
from apps.payments.pricing.errors import ComponentNotAllowed
from apps.payments.pricing.http import domain_read_actions, require_domain, require_pricing, space_for
from apps.payments.pricing.impact import impact
from apps.payments.pricing.rates import RateCard
from apps.payments.pricing.serializers import (
    PricingCurrencySerializer, PricingImpactSerializer, PricingDefaultSerializer, PricingDefaultWriteSerializer,
    RentalTimingSerializer,
)

TAGS = ["Pricing"]
WRITE_ERRORS = errors(400, 401, 403, 404, 423, e403="`setting_not_delegated` or `setting_locked`.",
                      e404="Space not visible, the area's module is off (`pricing_domain_unknown`) or "
                           "`charges.pricing` is off (`pricing_disabled`).")


def _space(request, makerspace_id, domain, *, lock=False):
    space = space_for(request.user, makerspace_id, *domain_read_actions(domain), lock=lock)
    require_pricing(space)
    require_domain(space, domain)
    return space


class PricingDefaultView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read one area's rate card (free/paid, rates, caps)",
                   description="Space Manager, the area's manager, or view_finance. `editable` says whether "
                               "the caller may save it; `refusal` names why not.",
                   responses={200: PricingDefaultSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, domain):
        space = _space(request, makerspace_id, domain)
        return Response(PricingDefaultSerializer(card_payload(RateCard(space, domain), request.user)).data)

    @extend_schema(tags=TAGS, summary="Change one area's rate card",
                   description="Settings authority: the Space Manager, or the area's manager holding its "
                               "settings grant. Lending also writes the deposit and late-fee block (the same "
                               "columns `payment-settings` edits). Run the impact preview first: items that "
                               "inherit the default change price; custom and Free items never do (A13). "
                               "Membership is read-only here (plans own their prices).",
                   request=PricingDefaultWriteSerializer,
                   responses={200: PricingDefaultSerializer, **WRITE_ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, domain):
        space = _space(request, makerspace_id, domain)
        if domain not in SETTINGS_MODULES:
            raise ComponentNotAllowed("Membership prices are set on each plan.")
        body = PricingDefaultWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        admin_services.set_default(request.user, space, domain, mode=data.get("mode"), lines=data.get("lines", ()),
                                   loan_block=data.get("lending"), failed_job_charge=data.get("failed_job_charge"))
        return Response(PricingDefaultSerializer(card_payload(RateCard(space, domain), request.user)).data)


class PricingImpactView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Preview which items a rate-card change would reprice",
                   description="Nothing is saved. Lists up to 200 item/component pairs whose effective price "
                               "moves, with the total count.",
                   request=PricingDefaultWriteSerializer, responses={200: PricingImpactSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id, domain):
        space = _space(request, makerspace_id, domain)
        body = PricingDefaultWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        result = impact(space, domain, mode=data.get("mode"), lines=data.get("lines", ()),
                        loan_block=data.get("lending"))
        return Response(PricingImpactSerializer(result).data)


def _timing_payload(space, actor):
    from apps.makerspaces.settings_authority import decide

    decision = decide(actor, space, "inventory", "rental_timing")
    return {"rental_timing": RateCard(space, "loans").rental_timing, "editable": decision.allowed,
            "via": decision.via, "locked": decision.locked}


class RentalTimingView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read when per-day rental is charged",
                   responses={200: RentalTimingSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id, "loans")
        return Response(RentalTimingSerializer(_timing_payload(space, request.user)).data)

    @extend_schema(tags=TAGS, summary="Choose when per-day rental is charged",
                   description="`at_checkout` charges the planned days at issue; `at_return` the actual days at "
                               "return. The Space Manager or the Inventory Manager (no settings grant needed, "
                               "#128 C-11d); a Space Manager lock still refuses. Applies to loans issued after "
                               "the change; audited as `settings.changed`.",
                   request=RentalTimingSerializer, responses={200: RentalTimingSerializer, **WRITE_ERRORS})
    def put(self, request, makerspace_id):
        space = _space(request, makerspace_id, "loans")
        body = RentalTimingSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin_services.set_rental_timing(request.user, space, body.validated_data["rental_timing"])
        return Response(RentalTimingSerializer(_timing_payload(space, request.user)).data)


class PricingCurrencyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read the currency new charges are raised in",
                   responses={200: PricingCurrencySerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE)
        require_pricing(space)
        return Response({"default_currency": RateCard(space, "loans").currency})

    @extend_schema(tags=TAGS, summary="Change the currency new charges are raised in",
                   description="Space Manager only (a finance setting). Works with the online-payment rail "
                               "switched off or tombstoned; existing charges keep their currency.",
                   request=PricingCurrencySerializer, responses={200: PricingCurrencySerializer, **WRITE_ERRORS})
    def put(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE)
        require_pricing(space)
        body = PricingCurrencySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        currency = admin_services.set_currency(request.user, space, body.validated_data["default_currency"])
        return Response({"default_currency": currency}, status=200)

