"""Seat claims, ticket transfers, type changes and series passes for members (release 2 L6)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from .models import EventPassType, EventRegistration, EventSeries
from .serializers_ticketing_orders import (
    ClaimInputSerializer, ClaimPreviewSerializer, ClaimResultSerializer, OrderPlacedSerializer, OrderSerializer,
)
from .views_ticketing_orders import ERRORS, MemberOrderView


def _first_name(user):
    return (user.first_name or user.display_name or "Someone").split(" ")[0]


class TicketClaimView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Preview a seat someone bought for me", request=None,
                   responses={200: ClaimPreviewSerializer, **ERRORS})
    def get(self, request, token):
        from .orders_claims import find_claim
        seat = find_claim(token)
        email = (request.user.email or "").strip().lower()
        return Response({"event_id": seat.event_id, "makerspace_id": seat.event.makerspace_id,
                         "event_title": seat.event.title, "starts_at": seat.event.starts_at,
                         "ticket_type": seat.line.ticket_type.name if seat.line.ticket_type_id else seat.line.label,
                         "from_name": _first_name(seat.order.buyer),
                         "email_matches": bool(email) and email == seat.attendee_email.strip().lower()})

    @extend_schema(tags=["Member events"], summary="Claim the seat: it becomes my registration",
                   request=ClaimInputSerializer, responses={201: ClaimResultSerializer, **ERRORS})
    def post(self, request, token):
        from .orders_claims import claim
        body = ClaimInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        registration = claim(token, user=request.user, values=dict(body.validated_data))
        return Response({"registration_id": registration.pk, "event_id": registration.event_id,
                         "status": registration.status}, status=201)


class TransferInputSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TransferResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()


class TicketTransferOfferView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Offer my ticket to someone else (they accept by email link)",
                   request=TransferInputSerializer, responses={201: TransferResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .transfers import offer_transfer
        space = self.space(makerspace_id)
        registration = get_object_or_404(EventRegistration, pk=pk, member=request.user, event__makerspace=space)
        body = TransferInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        transfer = offer_transfer(registration, actor=request.user, to_email=body.validated_data["email"])
        return Response({"id": transfer.pk, "status": transfer.status, "expires_at": transfer.expires_at}, status=201)


class TicketTransferAcceptView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Preview a ticket offered to me", request=None,
                   responses={200: ClaimPreviewSerializer, **ERRORS})
    def get(self, request, token):
        from .transfers import find_offer
        transfer = find_offer(token)
        event, registration = transfer.registration.event, transfer.registration
        email = (request.user.email or "").strip().lower()
        return Response({"event_id": event.pk, "makerspace_id": event.makerspace_id, "event_title": event.title,
                         "starts_at": event.starts_at,
                         "ticket_type": registration.ticket_type.name if registration.ticket_type_id else "",
                         "from_name": _first_name(transfer.from_member), "email_matches": email == transfer.to_email})

    @extend_schema(tags=["Member events"], summary="Accept the ticket: the registration becomes mine",
                   request=None, responses={201: ClaimResultSerializer, **ERRORS})
    def post(self, request, token):
        from .transfers import accept
        registration = accept(token, user=request.user)
        return Response({"registration_id": registration.pk, "event_id": registration.event_id,
                         "status": registration.status}, status=201)


class TypeChangeInputSerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField(min_value=1)
    digest = serializers.CharField(max_length=64, required=False, allow_blank=True)


class TypeChangeResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("changed", "payment_required"))
    registration_id = serializers.IntegerField()
    order = OrderSerializer(allow_null=True)
    checkout_url = serializers.CharField(allow_blank=True)


class TicketTypeChangeView(MemberOrderView):
    @extend_schema(tags=["Member events"], summary="Change my ticket type (pay the difference, or get it back)",
                   request=TypeChangeInputSerializer, responses={200: TypeChangeResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        from .orders_type_change import change_type
        space = self.space(makerspace_id)
        registration = get_object_or_404(EventRegistration, pk=pk, member=request.user, event__makerspace=space)
        body = TypeChangeInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = change_type(registration, actor=request.user, ticket_type_id=body.validated_data["ticket_type_id"],
                             digest=body.validated_data.get("digest") or None)
        order = OrderSerializer(result["order"], context={"request": request}).data if result["order"] else None
        return Response({"status": result["status"], "registration_id": registration.pk, "order": order,
                         "checkout_url": order["checkout_url"] if order else ""})


class PassTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventPassType
        fields = ("id", "name", "amount", "capacity", "occurrence_refund_amount", "sales_end_at", "is_active")


class PassBuySerializer(serializers.Serializer):
    pass_type_id = serializers.IntegerField(min_value=1)
    digest = serializers.CharField(max_length=64, required=False, allow_blank=True)


class MemberSeriesPassView(MemberOrderView):
    def series(self, makerspace_id, series_id):
        return get_object_or_404(EventSeries.objects.select_related("makerspace"), pk=series_id,
                                 makerspace=self.space(makerspace_id), is_public=True)

    @extend_schema(tags=["Member events"], summary="Passes on sale for a series", request=None,
                   responses={200: PassTypeSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, series_id):
        from .passes import _require_feature
        series = self.series(makerspace_id, series_id)
        _require_feature(series)
        return Response(PassTypeSerializer(series.pass_types.filter(is_active=True), many=True).data)

    @extend_schema(tags=["Member events"], summary="Buy a pass covering every upcoming occurrence",
                   request=PassBuySerializer, responses={201: OrderPlacedSerializer, **ERRORS})
    def post(self, request, makerspace_id, series_id):
        from .passes import place_pass_order
        series = self.series(makerspace_id, series_id)
        body = PassBuySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        order, _payment = place_pass_order(series, member=request.user, actor=request.user,
                                           pass_type_id=body.validated_data["pass_type_id"],
                                           digest=body.validated_data.get("digest") or None)
        order.refresh_from_db()
        data = OrderSerializer(order, context={"request": request}).data
        return Response({"order": data, "checkout_url": data["checkout_url"]}, status=201)
