"""Decision 242(g): an event's loans and guest passes, READ-ONLY, for whoever manages that event.

The Event Manager holds neither `issue_request`/`view_inventory` nor `manage_members`, so the event's equipment
and guests were invisible to them. These two lists are scoped to ONE event the actor already manages
(`event_authority.get_event`): loans through the event's own loan context, passes through the event-pass
`operation_id` (`event-<event>-reg-<registration>`). Quantities are the loan's own (requested, issued, returned);
no stock counts, no other guests, no member contact details. The same payloads are never writable here.
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events.views_admin_event_detail import _manageable_event
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import feature_enabled, module_enabled

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (401, 403, 404)}
LIMIT = 200


class EventLoanItemSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    requested = serializers.IntegerField()
    issued = serializers.IntegerField()
    returned = serializers.IntegerField()


class EventLoanSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    status = serializers.CharField()
    holder = serializers.CharField(help_text="Readable borrower label.")
    issued_at = serializers.DateTimeField(allow_null=True)
    due_at = serializers.DateTimeField(allow_null=True)
    items = EventLoanItemSerializer(many=True)


class EventLoansSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="False when loans are switched off for this space.")
    results = EventLoanSerializer(many=True)


class EventGuestPassSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    status = serializers.CharField()
    holder = serializers.CharField(help_text="Account username only.")
    valid_until = serializers.DateTimeField()


class EventGuestPassesSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="False when guest passes are off for this space.")
    results = EventGuestPassSerializer(many=True)


class EventLoansView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="This event's equipment loans (read-only)",
                   responses={200: EventLoansSerializer, **ERRORS})
    def get(self, request, pk):
        from apps.events.models_loan_context import EventLoanContext
        from apps.hardware_requests.display import requester_label
        from apps.hardware_requests.models import HardwareRequest

        event = _manageable_event(request.user, pk)
        space = event.makerspace
        if not (feature_enabled(space, "loans.enabled") and module_enabled(space, "request_workflow")):
            return Response({"enabled": False, "results": []})
        ids = EventLoanContext.objects.filter(event=event, makerspace=space, active=True).values("request_id")
        rows = HardwareRequest.objects.filter(makerspace=space, pk__in=ids).select_related("requester").prefetch_related(
            "items__product").order_by("-pk")[:LIMIT]
        return Response({"enabled": True, "results": [{
            "request_id": row.pk, "status": row.status, "holder": requester_label(row),
            "issued_at": row.issued_at, "due_at": row.return_due_at,
            "items": [{"product_name": item.product.name, "requested": item.requested_quantity,
                       "issued": item.issued_quantity, "returned": item.returned_quantity}
                      for item in row.items.all()],
        } for row in rows]})


class EventGuestPassesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Guest passes issued for this event (read-only)",
                   responses={200: EventGuestPassesSerializer, **ERRORS})
    def get(self, request, pk):
        from apps.makerspaces.models import GuestPass

        event = _manageable_event(request.user, pk)
        space = event.makerspace
        if not feature_enabled(space, "membership.guest_passes"):
            return Response({"enabled": False, "results": []})
        base = f"event-{event.pk}-reg-"
        rows = GuestPass.objects.filter(makerspace=space, kind=GuestPass.Kind.EVENT).filter(
            Q(operation_id__startswith=base)).select_related("holder").order_by("-pk")[:LIMIT]
        return Response({"enabled": True, "results": [{
            "id": row.pk, "kind": row.kind, "status": row.status, "holder": row.holder.username,
            "valid_until": row.valid_until} for row in rows]})
