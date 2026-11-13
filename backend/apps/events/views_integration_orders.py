"""`orders:read` (release 2 L6, G35): signed server reads of ticket orders, keyset-paginated.

HMAC server clients only, bound to their tenant, behind `events.api_read` and
`events.orders` (both must be on, else 404 like any unknown route). Each row is the
order's money and seats: totals, frozen lines, and how many seats are claimed. No buyer
or attendee contact, name, claim token or payment provider handle ever leaves.
"""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.apiclients.read_contract import SignedReadView, keyset_page
from apps.apiclients.scope_registry_reads import ORDER_READ
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable

from .models import EventOrder
from .views_integration import ERRORS, HMAC_PARAMETERS, PAGE_PARAMETERS


class IntegrationOrderLineSerializer(serializers.Serializer):
    kind = serializers.CharField()
    label = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_amount = MoneyField(max_digits=13, decimal_places=3)
    discount_amount = MoneyField(max_digits=13, decimal_places=3)
    line_total = MoneyField(max_digits=13, decimal_places=3)
    ticket_type_id = serializers.IntegerField(allow_null=True)
    addon_id = serializers.IntegerField(allow_null=True)


class IntegrationOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField(allow_null=True)
    series_id = serializers.IntegerField(allow_null=True)
    kind = serializers.CharField()
    status = serializers.CharField()
    currency = serializers.CharField()
    subtotal = MoneyField(max_digits=13, decimal_places=3)
    discount_total = MoneyField(max_digits=13, decimal_places=3)
    fee_total = MoneyField(max_digits=13, decimal_places=3)
    total = MoneyField(max_digits=13, decimal_places=3)
    seats = serializers.IntegerField(source="seat_total")
    seats_claimed = serializers.IntegerField(source="seat_claimed")
    created_at = serializers.DateTimeField()
    paid_at = serializers.DateTimeField(allow_null=True)
    lines = IntegrationOrderLineSerializer(many=True, source="lines.all")


class IntegrationOrderPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = IntegrationOrderSerializer(many=True)


class OrderIntegrationReadView(SignedReadView):
    required_scopes = (ORDER_READ,)

    def orders(self, request):
        tenant = request.api_client.makerspace
        if not is_servable(tenant) or not module_enabled(tenant, "events"):
            raise NotFound()
        if not feature_enabled(tenant, "events.api_read") or not feature_enabled(tenant, "events.orders"):
            raise NotFound()
        return (EventOrder.objects.filter(makerspace=tenant).prefetch_related("lines")
                .annotate(seat_total=Count("seats", filter=~Q(seats__status="void")),
                          seat_claimed=Count("seats", filter=Q(seats__status="claimed"))))


class IntegrationOrderListView(OrderIntegrationReadView):
    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}],
                   summary="Read ticket orders (server HMAC; orders:read)", parameters=PAGE_PARAMETERS,
                   responses={200: IntegrationOrderPageSerializer, **ERRORS})
    def get(self, request):
        rows, cursor = keyset_page(request, self.orders(request), subject="orders")
        return Response({"next_cursor": cursor, "results": IntegrationOrderSerializer(rows, many=True).data})


class IntegrationOrderDetailView(OrderIntegrationReadView):
    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}],
                   summary="Read one ticket order (server HMAC; orders:read)", parameters=HMAC_PARAMETERS,
                   responses={200: IntegrationOrderSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(IntegrationOrderSerializer(get_object_or_404(self.orders(request), pk=pk)).data)
