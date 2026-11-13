"""Hack-money per-space event money settings: prize tax (#181 G7) and accepted payee templates (G13).

Space Manager only (`manage_makerspace`) and never delegated to an event or organization grant.
Prize tax is RECORD ONLY: the setting proposes a deduction on a prize payout; staff deduct it and
file it outside SpaceWorks. No certificates and no filing reports exist.
"""

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.payments.models import EventMoneySettings

ERRORS = {status: ErrorSerializer for status in (400, 401, 403, 404, 409)}
FIELDS = ("prize_tds_enabled", "prize_tds_rate", "prize_tds_threshold", "payee_templates")


class EventMoneySettingsRead(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    version = serializers.IntegerField()
    prize_tds_enabled = serializers.BooleanField()
    prize_tds_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    prize_tds_threshold = MoneyField(max_digits=13, decimal_places=3)
    payee_templates = serializers.ListField(child=serializers.ListField(child=serializers.CharField()))
    available_payee_templates = serializers.ListField(child=serializers.ListField(child=serializers.CharField()),
                                                      help_text="Country/method pairs inside the deployment ceiling.")
    currency = serializers.CharField()


class EventMoneySettingsInput(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)
    prize_tds_enabled = serializers.BooleanField(required=False)
    prize_tds_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"),
                                              max_value=Decimal("100"), required=False)
    prize_tds_threshold = MoneyField(max_digits=13, decimal_places=3, min_value=Decimal("0"),
                                                   required=False)
    payee_templates = serializers.ListField(child=serializers.ListField(child=serializers.CharField(max_length=16),
                                                                        min_length=2, max_length=2),
                                            max_length=200, required=False)


def projection(row, space):
    from apps.payments.event_payouts.space_templates import deployment_ceiling
    from apps.payments.event_payouts.templates import operator_templates
    from apps.payments.models import MakerspacePaymentSettings
    from django.conf import settings
    operator = getattr(settings, "EVENT_PAYOUT_TENANT_POLICIES", {}).get(str(space.pk))
    ceiling = operator_templates(space.pk)[0] if operator else deployment_ceiling()
    return {"makerspace_id": space.pk, "version": row.version, **{key: getattr(row, key) for key in FIELDS},
            "available_payee_templates": sorted([country, method] for country, method, *_ in ceiling),
            "currency": MakerspacePaymentSettings.for_makerspace(space).default_currency}


class EventMoneySettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def _space(self, request, makerspace_id):
        return get_object_or_404(rbac.scope_by_action(
            request.user, rbac.Action.MANAGE_MAKERSPACE, servable_queryset(), field="pk"), pk=makerspace_id)

    @extend_schema(tags=["Payments"], summary="Read the space's prize tax and payee settings",
                   description="Requires manage_makerspace. Prize tax is record-only and off by default.",
                   responses={200: EventMoneySettingsRead, **ERRORS})
    def get(self, request, makerspace_id):
        space = self._space(request, makerspace_id)
        return Response(projection(EventMoneySettings.for_makerspace(space), space))

    @extend_schema(tags=["Payments"], summary="Change the space's prize tax and payee settings",
                   description="Requires manage_makerspace. 409 stale_version; 400 payee_template_unsupported "
                               "for a pair outside the deployment ceiling. An empty payee list keeps the "
                               "operator's policy.",
                   request=EventMoneySettingsInput, responses={200: EventMoneySettingsRead, **ERRORS})
    @transaction.atomic
    def patch(self, request, makerspace_id):
        from rest_framework.exceptions import ValidationError
        from apps.payments.event_payouts.space_templates import validate_selection
        from apps.payments.event_payouts.validation import PayoutValidationError
        from apps.payments.event_payouts.errors import require
        space = self._space(request, makerspace_id)
        values = EventMoneySettingsInput(data=request.data)
        values.is_valid(raise_exception=True)
        data = values.validated_data
        row = EventMoneySettings.objects.select_for_update().filter(makerspace=space).first()
        require((row.version if row else 0) == data["expected_version"], "stale_version")
        row = row or EventMoneySettings(makerspace=space, version=0)
        if "payee_templates" in data:
            try:
                data["payee_templates"] = validate_selection(data["payee_templates"], space.pk)
            except PayoutValidationError as exc:
                raise ValidationError({"payee_templates": exc.code}) from None
        changed = sorted(key for key in FIELDS if key in data and data[key] != getattr(row, key))
        for key in changed:
            setattr(row, key, data[key])
        row.version += 1
        row.updated_by = request.user
        row.save()
        audit.record(request.user, "payment.event_money_settings_updated", makerspace=space, target=space,
                     meta={"fields": changed})
        return Response(projection(row, space))
