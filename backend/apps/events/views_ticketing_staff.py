"""Staff ticketing v2 (release 2 L6): add-ons, sales rules, orders and desk collection.

Organisers holding `manage_registrations` on the event run its add-ons, sales rules and
order list. Money policy -- the per-event refund override and venue fees -- stays with the
space's event staff (`manage_events` in the makerspace), never an outside organiser.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from .event_permissions import MANAGE_REGISTRATIONS
from .feature_gates import require_feature
from .models import EventAddon, EventOrder, EventSalesSettings
from .serializers_ticketing_staff import (
    AddonListSerializer, AddonSerializer, DeskCollectResultSerializer, DeskCollectSerializer,
    SalesSettingsSerializer, StaffOrderListSerializer, StaffOrderSerializer,
)
from .views_admin_event_detail import _manageable_event, _manageable_registration
from .views_invites import ERRORS, PAGE_PARAMETERS, paginated


class EventAddonListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, parameters=PAGE_PARAMETERS,
                   responses={200: AddonListSerializer, **ERRORS})
    def get(self, request, pk):
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        require_feature(event, "events.addons")
        return paginated(request, event.addons.prefetch_related("variants").order_by("pk"), AddonSerializer)

    @extend_schema(tags=["Admin events"], request=AddonSerializer, responses={201: AddonSerializer, **ERRORS})
    def post(self, request, pk):
        from .addons import create_addon
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        body = AddonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = dict(body.validated_data)
        addon = create_addon(event, actor=request.user, variants=values.pop("variants", []), **values)
        return Response(AddonSerializer(addon).data, status=201)


class EventAddonDetailView(APIView):
    permission_classes = [IsActiveStaff]

    def addon(self, request, pk):
        addon = get_object_or_404(EventAddon.objects.select_related("event__makerspace"), pk=pk)
        _manageable_event(request.user, addon.event_id, MANAGE_REGISTRATIONS)
        return addon

    @extend_schema(tags=["Admin events"], request=AddonSerializer, responses={200: AddonSerializer, **ERRORS})
    def patch(self, request, pk):
        from .addons import update_addon
        addon = self.addon(request, pk)
        body = AddonSerializer(addon, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        values = dict(body.validated_data)
        addon = update_addon(addon, actor=request.user, variants=values.pop("variants", None), **values)
        return Response(AddonSerializer(addon).data)

    @extend_schema(tags=["Admin events"], request=None, responses={204: None, **ERRORS})
    def delete(self, request, pk):
        from .addons import delete_addon
        delete_addon(self.addon(request, pk), actor=request.user)
        return Response(status=204)


class EventSalesSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, responses={200: SalesSettingsSerializer, **ERRORS})
    def get(self, request, pk):
        from .orders_quote import sales_settings
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        require_feature(event, "events.orders")
        return Response(SalesSettingsSerializer(sales_settings(event)).data)

    @extend_schema(tags=["Admin events"], request=SalesSettingsSerializer,
                   responses={200: SalesSettingsSerializer, **ERRORS})
    def put(self, request, pk):
        from django.db import transaction
        from apps.audit.services import record
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        require_feature(event, "events.orders")
        body = SalesSettingsSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            row, _ = EventSalesSettings.objects.select_for_update().get_or_create(
                event=event, defaults={"makerspace": event.makerspace})
            for key, value in body.validated_data.items():
                setattr(row, key, value)
            row.updated_by = request.user
            row.save()
            record(request.user, "event.sales_settings_updated", makerspace=event.makerspace, target=event,
                   meta={"fields": sorted(body.validated_data)})
        return Response(SalesSettingsSerializer(row).data)


class EventOrderListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, parameters=PAGE_PARAMETERS,
                   description="Orders with their seats: unclaimed seats stay visible to the organiser, "
                               "and a disputed payment is flagged (nothing is cancelled automatically).",
                   responses={200: StaffOrderListSerializer, **ERRORS})
    def get(self, request, pk):
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        require_feature(event, "events.orders")
        rows = (EventOrder.objects.filter(event=event) | EventOrder.objects.filter(
            seats__event=event, kind=EventOrder.Kind.PASS)).distinct()
        rows = rows.select_related("buyer", "event", "series").prefetch_related("lines", "seats__line")
        return paginated(request, rows.order_by("-created_at", "-pk"), StaffOrderSerializer)


class EventOrderDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None, responses={200: StaffOrderSerializer, **ERRORS})
    def get(self, request, pk):
        order = get_object_or_404(EventOrder.objects.select_related("buyer", "event", "series"), pk=pk)
        event_id = order.event_id or order.seats.values_list("event_id", flat=True).first()
        _manageable_event(request.user, event_id, MANAGE_REGISTRATIONS)
        return Response(StaffOrderSerializer(order, context={"request": request}).data)


class EventRegistrationCollectPaymentView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Collect a pending ticket payment at the check-in desk",
                   request=DeskCollectSerializer, responses={200: DeskCollectResultSerializer, **ERRORS})
    def post(self, request, pk):
        from .services_checkin import collect_at_desk
        registration = _manageable_registration(request.user, pk, "check_in")
        body = DeskCollectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = collect_at_desk(registration, actor=request.user, **body.validated_data)
        payment = result["payment"]
        return Response({"payment_id": payment.pk, "payment_status": payment.status,
                         "checkout_url": result["checkout_url"]})




class PayLinkInputSerializer(serializers.Serializer):
    send = serializers.BooleanField(default=False, help_text="Also email the link to the guest's account address.")


class PayLinkResultSerializer(serializers.Serializer):
    pay_link = serializers.CharField()
    sent = serializers.BooleanField()


class EventRegistrationPayLinkView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="The link a guest pays their ticket through (Add guest)",
                   request=PayLinkInputSerializer, responses={200: PayLinkResultSerializer, **ERRORS})
    def post(self, request, pk):
        from .orders_pay_link import pay_link
        registration = _manageable_registration(request.user, pk, MANAGE_REGISTRATIONS)
        body = PayLinkInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        url = pay_link(registration, actor=request.user, send=body.validated_data["send"])
        return Response({"pay_link": url, "sent": body.validated_data["send"]})
