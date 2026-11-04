"""Event money policy for the space's own staff (release 2 L6): the per-event refund policy,
venue fees for hosting, and series pass prices.

These decide what buyers and outside organisers owe or are owed, so they need
`manage_events` in the makerspace (the Event Manager or the Space Manager), not only an
organiser's event grant.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff

from .feature_gates import require_feature
from .models import EventPassType, EventVenueFee
from .serializers_admin import EmptyActionSerializer
from .serializers_ticketing_staff import (
    EventRefundPolicyInputSerializer, EventRefundPolicySerializer, PassTypeListSerializer, PassTypeStaffSerializer,
    VenueFeeInputSerializer, VenueFeeSerializer,
)
from .views_invites import ERRORS, PAGE_PARAMETERS, paginated


def money_event(actor, pk, *, series=False):
    from . import event_authority
    target = event_authority.get_event(actor, pk, None, series=series)
    if not rbac.can(actor, rbac.Action.MANAGE_EVENTS, target.makerspace_id):
        raise PermissionDenied()
    return target


def _policy(event):
    from .cancellation_policy import has_sales, policy_summary
    summary = policy_summary(event)
    return {**summary, "locked": has_sales(event)}


class EventRefundPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, responses={200: EventRefundPolicySerializer, **ERRORS})
    def get(self, request, pk):
        event = money_event(request.user, pk)
        require_feature(event, "events.refund_override")
        return Response(_policy(event))

    @extend_schema(tags=["Admin events"], summary="Set this event's own refund policy",
                   description="After the first sale the policy may only become more generous; anything else "
                               "answers 409 `policy_less_generous`.",
                   request=EventRefundPolicyInputSerializer, responses={200: EventRefundPolicySerializer, **ERRORS})
    def post(self, request, pk):
        from .cancellation_policy import OVERRIDE_FIELDS, set_override
        event = money_event(request.user, pk)
        body = EventRefundPolicyInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = body.validated_data
        set_override(event, actor=request.user, enabled=values["enabled"],
                     values={key: values[key] for key in OVERRIDE_FIELDS}, policy_text=values.get("policy_text", ""))
        return Response(_policy(event))


class EventVenueFeeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, responses={200: VenueFeeSerializer, **ERRORS})
    def get(self, request, pk):
        event = money_event(request.user, pk)
        require_feature(event, "events.venue_fees")
        fee = get_object_or_404(EventVenueFee.objects.select_related("payer", "event__makerspace"), event=event)
        return Response(VenueFeeSerializer(fee, context={"request": request}).data)

    @extend_schema(tags=["Admin events"], summary="Set who pays the venue fee and how much",
                   request=VenueFeeInputSerializer, responses={200: VenueFeeSerializer, **ERRORS})
    def put(self, request, pk):
        from apps.accounts.models import User
        from apps.bookings.models import BookableSpace
        from apps.organizations.models import Organization
        from .venue_fees import configure
        event = money_event(request.user, pk)
        body = VenueFeeInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = body.validated_data
        payer = get_object_or_404(User.objects.filter(is_active=True), pk=values["payer_id"])
        room = (get_object_or_404(BookableSpace, pk=values["room_id"], makerspace=event.makerspace)
                if values.get("room_id") else None)
        organization = (get_object_or_404(Organization, pk=values["organization_id"])
                        if values.get("organization_id") else None)
        fee = configure(event, actor=request.user, payer=payer, organization=organization, room=room,
                        mode=values["mode"], basis=values["basis"], amount=values.get("amount"))
        return Response(VenueFeeSerializer(fee, context={"request": request}).data)


class EventVenueFeeChargeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Charge the venue fee now (otherwise on publish)",
                   request=EmptyActionSerializer, responses={200: VenueFeeSerializer, **ERRORS})
    def post(self, request, pk):
        from .venue_fees import charge
        event = money_event(request.user, pk)
        fee, _payment = charge(event, actor=request.user)
        return Response(VenueFeeSerializer(fee, context={"request": request}).data)


class EventPassTypeListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, parameters=PAGE_PARAMETERS,
                   responses={200: PassTypeListSerializer, **ERRORS})
    def get(self, request, pk):
        from .passes import _require_feature
        series = money_event(request.user, pk, series=True)
        _require_feature(series)
        return paginated(request, series.pass_types.order_by("pk"), PassTypeStaffSerializer)

    @extend_schema(tags=["Admin events"], request=PassTypeStaffSerializer,
                   responses={201: PassTypeStaffSerializer, **ERRORS})
    def post(self, request, pk):
        from .passes import save_pass_type
        series = money_event(request.user, pk, series=True)
        body = PassTypeStaffSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = save_pass_type(series, actor=request.user, **body.validated_data)
        return Response(PassTypeStaffSerializer(row).data, status=201)


class EventPassTypeDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=PassTypeStaffSerializer,
                   responses={200: PassTypeStaffSerializer, **ERRORS})
    def patch(self, request, pk):
        from .passes import save_pass_type
        row = get_object_or_404(EventPassType.objects.select_related("series__makerspace"), pk=pk)
        series = money_event(request.user, row.series_id, series=True)
        body = PassTypeStaffSerializer(row, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        row = save_pass_type(series, actor=request.user, pass_type=row, **body.validated_data)
        return Response(PassTypeStaffSerializer(row).data)

