"""GET the linked finance view of one event (decision 216 item 8). Read-only; no money path.

Each section comes from its own owner and is omitted when its module or capability is off or
the caller lacks that section's authority (`event_linked_finance`). 404 when the space is not
servable, Events is off, the event is another tenant's, the caller cannot see the event, or
no section is visible.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import module_off
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.payments.event_linked_finance import linked_finance, may_view_event

MONEY = {"max_digits": 15, "decimal_places": 3}
ERRORS = {401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer)}


class ChargeTotalsSerializer(serializers.Serializer):
    currency = serializers.CharField()
    charges = serializers.IntegerField()
    owed = MoneyField(**MONEY, help_text="Pending: still owed.")
    paid_online = MoneyField(**MONEY, help_text="Captured by an online provider.")
    paid_offline = MoneyField(**MONEY, help_text="Settled offline against a ManualSettlement receipt.")
    offline_receipts = serializers.IntegerField(help_text="Effective ManualSettlement receipts (chain heads).")
    offline_by_method = serializers.DictField(child=MoneyField(**MONEY))
    waived = MoneyField(**MONEY)
    refunded = MoneyField(**MONEY, help_text="Succeeded, not superseded refunds.")


class RegistrationChargesSerializer(serializers.Serializer):
    owner = serializers.CharField()
    source = serializers.CharField()
    tracking_enabled = serializers.BooleanField()
    currencies = ChargeTotalsSerializer(many=True)


class VenueFeeSerializer(serializers.Serializer):
    owner = serializers.CharField()
    source = serializers.CharField()
    status = serializers.ChoiceField(choices=["none", "configured", "charged", "free"])
    currencies = ChargeTotalsSerializer(many=True)


class BookingRoomChargeSerializer(serializers.Serializer):
    owner = serializers.ChoiceField(choices=["bookings"])
    label = serializers.CharField()
    read_only = serializers.BooleanField()
    source = serializers.CharField()
    state = serializers.ChoiceField(choices=["linked", "booking_unavailable"])
    booking_ids = serializers.ListField(child=serializers.IntegerField(),
                                        help_text="The linked booking then each replacement, oldest first.")
    currencies = ChargeTotalsSerializer(many=True)


class ReimbursementTotalsSerializer(serializers.Serializer):
    currency = serializers.CharField()
    submitted_count = serializers.IntegerField()
    submitted = MoneyField(**MONEY)
    approved_count = serializers.IntegerField()
    approved = MoneyField(**MONEY)
    paid = MoneyField(**MONEY, help_text="The same money as `payouts.paid` for these claims; "
                                                       "never add the two.")


class ReimbursementsSerializer(serializers.Serializer):
    owner = serializers.CharField()
    source = serializers.CharField()
    currencies = ReimbursementTotalsSerializer(many=True)


class PayoutTotalsSerializer(serializers.Serializer):
    currency = serializers.CharField()
    obligations = serializers.IntegerField()
    approved = MoneyField(**MONEY)
    paid = MoneyField(**MONEY)
    remaining = MoneyField(**MONEY)
    paid_by_method = serializers.DictField(child=MoneyField(**MONEY))


class PayoutsSerializer(serializers.Serializer):
    owner = serializers.CharField()
    source = serializers.CharField()
    settlement = serializers.ChoiceField(choices=["offline"])
    currencies = PayoutTotalsSerializer(many=True)


class BudgetRowSerializer(serializers.Serializer):
    currency = serializers.CharField()
    income = MoneyField(**MONEY)
    refunds = MoneyField(**MONEY)
    other_income = MoneyField(**MONEY)
    expenses = MoneyField(**MONEY)
    payouts = MoneyField(**MONEY)
    budget = MoneyField(**MONEY, allow_null=True)
    budget_left = MoneyField(**MONEY, allow_null=True)
    net = MoneyField(**MONEY)


class BudgetSerializer(serializers.Serializer):
    owner = serializers.CharField()
    source = serializers.CharField()
    currencies = BudgetRowSerializer(many=True)


class SectionsSerializer(serializers.Serializer):
    registration_charges = RegistrationChargesSerializer(required=False)
    venue_fee = VenueFeeSerializer(required=False)
    booking_room_charge = BookingRoomChargeSerializer(required=False)
    reimbursements = ReimbursementsSerializer(required=False)
    payouts = PayoutsSerializer(required=False)
    budget = BudgetSerializer(required=False)


class EventLinkedFinanceSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    sections = SectionsSerializer(help_text="Only the sections the caller may see; hidden sections are omitted.")


class EventLinkedFinanceView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Finance"], operation_id="finance_event_linked_retrieve",
        summary="One event's linked finance: charges, venue or booking room charge, reimbursements, payouts, budget",
        description="Read-only. Each section is read from its own owner and omitted when its module or capability "
                    "is off or the caller lacks that section's authority. The booking room charge is Booking-owned "
                    "and never added to event totals. Amounts never mix currencies.",
        responses={200: EventLinkedFinanceSerializer, **ERRORS})
    def get(self, request, makerspace_id, event_id):
        from apps.events.models import Event
        from apps.makerspaces.origin_scope import origin_scoped_makerspace_id

        space = get_object_or_404(servable_queryset(), pk=makerspace_id)
        origin = origin_scoped_makerspace_id(request)
        if origin is not None and origin != space.pk:
            raise NotFound()
        if not module_enabled(space, "events"):
            raise module_off("events")  # typed 404 (#183B gap 12)
        event = get_object_or_404(Event.objects.filter(makerspace=space), pk=event_id)
        if not may_view_event(request.user, space, event):
            raise NotFound()
        sections = linked_finance(request, space, event)
        if not sections:
            raise NotFound()
        return Response(EventLinkedFinanceSerializer({"event_id": event.pk, "sections": sections}).data)


__all__ = ["EventLinkedFinanceView"]
