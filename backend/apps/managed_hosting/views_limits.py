"""Superadmin per-space limit overrides and the read-only request-rate table (#234)."""

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.makerspaces.limits_validation import validate_resource_limit_overrides
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from . import throttle_rates
from .limit_services import replace_space_overrides
from .limits_console import limit_rows
from .models import PlatformThrottleRate

TAGS = ["Managed hosting"]


class LimitRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.CharField()
    effective = serializers.IntegerField(allow_null=True)
    source = serializers.ChoiceField(
        choices=["own", "override", "plan", "default", "unlimited"],
        help_text="Where the value comes from: the space override, a hosted space's plan, the platform `default` (decision 328a), or `unlimited`.")
    area = serializers.CharField(required=False, help_text="Console group: people, inventory, machines, events, bookings, shop, money, messaging, integrations or storage.")
    group = serializers.CharField(required=False, help_text="Module group the row is shown under (`groups`); decision 328a.")
    module = serializers.CharField(required=False, help_text="The module that owns this limit.")
    platform_default = serializers.IntegerField(required=False, allow_null=True,
                                                help_text="The platform default for this key, null = none (decision 328a).")
    override = serializers.IntegerField(allow_null=True)
    has_override = serializers.BooleanField()
    used = serializers.IntegerField(allow_null=True)
    suggested = serializers.IntegerField(
        allow_null=True, help_text="A built-in fair-use value shown next to an empty field; never enforced.")


class PlatformLimitRowSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="`platform_{email,sms,whatsapp,push,wallet}_monthly`, "
                                          "`platform_payments_monthly_count` or `platform_payments_monthly_amount`.")
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=["count", "amount", "bytes", "per_minute"])
    limit = serializers.IntegerField(allow_null=True, help_text="null = unlimited (the default).")
    area = serializers.CharField(required=False)
    group = serializers.CharField(required=False)
    module = serializers.CharField(required=False)
    platform_default = serializers.IntegerField(required=False, allow_null=True)
    level = serializers.CharField(required=False)
    used = serializers.IntegerField(allow_null=True, help_text="This month (platform-credential path only for platform_* keys).")
    percent = serializers.FloatField(allow_null=True)


class AreaSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField(help_text="Translated group name.")


class SpaceLimitsSerializer(serializers.Serializer):
    areas = AreaSerializer(many=True, required=False)
    groups = AreaSerializer(many=True, required=False, help_text="Module groups in the order of the module switch screens.")
    quota_rows = PlatformLimitRowSerializer(
        many=True, required=False,
        help_text="Quotas on ANY space, each with its console `area`: events_monthly, bookings_monthly, "
                  "payments_monthly_count, payments_monthly_amount plus every decision-284 resource key "
                  "(event_registrations_monthly, shop_orders_monthly, shop_products, membership_plans, "
                  "donation_campaigns, bookable_spaces, boxes, organizations_linked, api_requests_per_minute, "
                  "analytics_connections, report_exports_monthly, kiosk_stations, devices, machine_jobs_monthly, "
                  "machine_sessions_monthly, storage_evidence_bytes, storage_public_images_bytes, webhook_endpoints). "
                  "null limit = no limit (the default). Group rows by `area` using `areas`.")
    custom_domain = serializers.BooleanField()
    hosting_type = serializers.ChoiceField(choices=["own", "hosted"])
    hosting_active = serializers.BooleanField(help_text="Hosting other makerspaces is on; when off every space is own.")
    hosted = serializers.BooleanField(help_text="Limits, plans, trials and hosting billing apply to this space.")
    rows = LimitRowSerializer(many=True)
    platform_rows = PlatformLimitRowSerializer(
        many=True, help_text="Monthly allowance of the PLATFORM credentials; every space, own or hosted.")


class SpaceLimitsUpdateSerializer(serializers.Serializer):
    overrides = serializers.DictField(
        help_text="The COMPLETE override map: a number, -1 or null (unlimited) per key, or the boolean "
                  "`custom_domain`. A key left out has no override and falls back to the plan.")


class RequestRateSerializer(serializers.Serializer):
    scope = serializers.CharField()
    default = serializers.CharField(help_text="The env/settings value; restored when the override is removed.")
    rate = serializers.CharField(help_text="The effective rate.")
    overridden = serializers.BooleanField()
    min_rate = serializers.CharField(help_text="Slowest allowed, as requests per hour.")
    max_rate = serializers.CharField(help_text="Fastest allowed, as requests per hour.")
    env_key = serializers.CharField()


class RequestRateUpdateSerializer(serializers.Serializer):
    rate = serializers.CharField(max_length=16, help_text="`N/sec`, `N/min`, `N/hour` or `N/day`.")


class SpaceLimitsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    # No `require_plans_enabled()` any more: the `platform_*` keys apply to every space whatever the
    # hosting switch says (owner 2026-11-11). Plan rows still resolve to "own"/unlimited when hosting is off.

    @extend_schema(tags=TAGS, summary="Read a space's limits with current usage",
                   responses={200: SpaceLimitsSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        return Response(limit_rows(get_object_or_404(Makerspace, pk=makerspace_id)))

    @extend_schema(tags=TAGS, summary="Replace a space's limit overrides", request=SpaceLimitsUpdateSerializer,
                   responses={200: SpaceLimitsSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        body = SpaceLimitsUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        new = validate_resource_limit_overrides(body.validated_data["overrides"])
        return Response(limit_rows(replace_space_overrides(request.user, makerspace_id, new)))


def _rate_rows():
    default = throttle_rates.defaults()
    over = throttle_rates.overrides()
    rows = []
    for scope in sorted(default):
        low, high = throttle_rates.bounds(scope)
        rows.append({"scope": scope, "default": default[scope], "rate": over.get(scope, default[scope]),
                     "overridden": scope in over, "min_rate": f"{low * 3600:g}/hour",
                     "max_rate": f"{high * 3600:g}/hour", "env_key": f"THROTTLE_{scope.upper()}"})
    return rows


class RequestRatesView(APIView):
    """Deployment-wide DRF throttles: env defaults, superadmin overrides within bounds."""

    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read the deployment-wide request rate limits",
                   responses={200: RequestRateSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        return Response(_rate_rows())


class RequestRateDetailView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Override one request rate (within safe bounds)",
                   request=RequestRateUpdateSerializer,
                   responses={200: RequestRateSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, scope):
        if scope not in throttle_rates.defaults():
            raise Http404()
        body = RequestRateUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            rate = throttle_rates.validate(scope, body.validated_data["rate"])
        except ValueError as exc:
            raise serializers.ValidationError({"rate": str(exc)}) from exc
        with transaction.atomic():
            before = PlatformThrottleRate.objects.filter(scope=scope).values_list("rate", flat=True).first()
            row, _ = PlatformThrottleRate.objects.update_or_create(
                scope=scope, defaults={"rate": rate, "updated_by": request.user})
            audit.record(request.user, "managed_hosting.throttle_rate_changed", makerspace=None, target=row,
                         meta={"scope": scope, "from": before, "to": rate})
        return Response(next(r for r in _rate_rows() if r["scope"] == scope))

    @extend_schema(tags=TAGS, summary="Restore a request rate to its env default",
                   responses={200: RequestRateSerializer, **errors(401, 403, 404)})
    def delete(self, request, scope):
        if scope not in throttle_rates.defaults():
            raise Http404()
        with transaction.atomic():
            row = PlatformThrottleRate.objects.filter(scope=scope).first()
            if row is not None:
                before = row.rate
                row.delete()
                audit.record(request.user, "managed_hosting.throttle_rate_changed", makerspace=None, target=None,
                             meta={"scope": scope, "from": before, "to": None})
        return Response(next(r for r in _rate_rows() if r["scope"] == scope))
