"""Member ticket orders (release 2 L6, G27/G28): quote, place, list, attendees, chase, cancel."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset

from .models import Event, EventOrder
from .serializers_admin import EmptyActionSerializer
from .serializers_ticketing_orders import (
    AttendeeAssignmentSerializer, ClaimResultSerializer, OrderListSerializer, OrderPlacedSerializer,
    OrderQuoteResponseSerializer, OrderRequestSerializer, OrderSerializer, TicketClaimInputSerializer,
)

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=text) for code, text in (
    (400, "Invalid body, an order rule (`order_limit`, `amount_below_minimum`) or the feature is off."),
    (401, "Sign in first."), (403, "This account cannot buy here."),
    (404, "Event, order or code not found (`access_code_invalid`)."),
    (409, "`sold_out`, `hold_expired`, `price_changed`, `already_registered` or `order_not_payable`."),
    (423, "The space is frozen for a move."),
)}


class MemberOrderView(APIView):
    permission_classes = [IsAuthenticated]
    # DRF's own scoped throttle (rate in settings), so the claim-route guard has no custom hook to review.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "event_orders"

    def space(self, makerspace_id):
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        require_module_for_servable(space, "events")
        return space

    def event(self, makerspace_id, event_id):
        space = self.space(makerspace_id)
        return get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id, makerspace=space,
                                 is_public=True, status=Event.Status.PUBLISHED)

    def order(self, request, makerspace_id, order_id):
        space = self.space(makerspace_id)
        return get_object_or_404(EventOrder.objects.select_related("event", "series", "makerspace"),
                                 pk=order_id, makerspace=space, buyer=request.user)


def _request(data):
    body = OrderRequestSerializer(data=data)
    body.is_valid(raise_exception=True)
    return dict(body.validated_data)


class MemberOrderQuoteView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Price a basket of tickets and add-ons (no seats held)",
                   request=OrderRequestSerializer, responses={200: OrderQuoteResponseSerializer, **ERRORS})
    def post(self, request, makerspace_id, event_id):
        from apps.payments.pricing.serializers import quote_payload
        from .cancellation_policy import policy_summary
        from .orders_checkout import addons_only, require_orderable
        from .orders_quote import build_quote
        event = self.event(makerspace_id, event_id)
        values = _request(request.data)
        require_orderable(event, request.user, values)
        priced = build_quote(event, request.user, values, addons_only=addons_only(event, request.user, values))
        return Response({"quote": quote_payload(priced.quote), "seats": priced.seats,
                         "promo_saving": (priced.quote.promo or {}).get("saving"), "policy": policy_summary(event)})


class MemberOrderListCreateView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="My ticket orders in this space", request=None,
                   responses={200: OrderListSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        from .views_invites import paginated
        space = self.space(makerspace_id)
        rows = (EventOrder.objects.filter(makerspace=space, buyer=request.user)
                .select_related("event", "series").prefetch_related("lines", "seats__line"))
        return paginated(request, rows, OrderSerializer)


class MemberEventOrderCreateView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Place an order: quote, hold the seats, raise one charge",
                   description="Answers the order and, when the space takes online payments, the checkout link. "
                               "A free order is paid at once; the buyer's own seat becomes their registration.",
                   request=OrderRequestSerializer, responses={201: OrderPlacedSerializer, **ERRORS})
    def post(self, request, makerspace_id, event_id):
        from .orders_checkout import place_order
        event = self.event(makerspace_id, event_id)
        values = _request(request.data)
        order, payment = place_order(event, member=request.user, actor=request.user, request=values,
                                     digest=values.pop("digest", None) or None)
        order.refresh_from_db()
        data = OrderSerializer(order, context={"request": request}).data
        return Response({"order": data, "checkout_url": data["checkout_url"]}, status=201)


class MemberOrderDetailView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="One of my orders, with its seats and who claimed them",
                   request=None, responses={200: OrderSerializer, **ERRORS})
    def get(self, request, makerspace_id, order_id):
        order = self.order(request, makerspace_id, order_id)
        return Response(OrderSerializer(order, context={"request": request}).data)


class MemberOrderAttendeesView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Name or rename the people for unclaimed seats",
                   request=AttendeeAssignmentSerializer, responses={200: OrderSerializer, **ERRORS})
    def post(self, request, makerspace_id, order_id):
        from .orders_attendees import assign_attendees
        order = self.order(request, makerspace_id, order_id)
        body = AttendeeAssignmentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        order = assign_attendees(order, member=request.user, assignments=body.validated_data["assignments"])
        return Response(OrderSerializer(order, context={"request": request}).data)


class MemberOrderChaseView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Re-send the claim link to attendees who have not claimed",
                   request=EmptyActionSerializer, responses={200: OrderSerializer, **ERRORS})
    def post(self, request, makerspace_id, order_id):
        from .orders_attendees import chase
        order = self.order(request, makerspace_id, order_id)
        chase(order, member=request.user)
        order.refresh_from_db()
        return Response(OrderSerializer(order, context={"request": request}).data)


class MemberOrderCancelView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Abandon an unpaid order: release its seats, void its charge",
                   request=EmptyActionSerializer, responses={200: OrderSerializer, **ERRORS})
    def post(self, request, makerspace_id, order_id):
        from .orders_cancel import cancel_pending_order
        order = self.order(request, makerspace_id, order_id)
        order = cancel_pending_order(order, actor=request.user)
        return Response(OrderSerializer(order, context={"request": request}).data)


class MemberOrderSeatClaimView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Take my own seat in a paid order (forms and waivers apply)",
                   request=TicketClaimInputSerializer, responses={201: ClaimResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, order_id, seat_id):
        from .orders_claims import claim_own_seat
        order = self.order(request, makerspace_id, order_id)
        body = TicketClaimInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        registration = claim_own_seat(order, seat_id, member=request.user, values=dict(body.validated_data))
        return Response({"registration_id": registration.pk, "event_id": registration.event_id,
                         "status": registration.status}, status=201)
