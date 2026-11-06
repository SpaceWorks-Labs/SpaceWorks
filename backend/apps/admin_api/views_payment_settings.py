from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.accounts import rbac
from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_payments import (
    MakerspacePaymentSettingsSerializer,
    PaymentProviderConflictSerializer,
    PaymentSettingsErrorSerializer,
    StripeConnectOnboardingSerializer,
)
from apps.audit import services as audit
from apps.makerspaces.domain_verification import is_self_host
from apps.makerspaces.guards import module_off, require_module
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.payments.connect import create_onboarding
from apps.payments.credential_validation import MAKERSPACE_CREDENTIAL_FIELDS
from apps.payments.models import MakerspacePaymentSettings
from apps.payments.stripe_client import PaymentsUnavailable


class MakerspacePaymentSettingsView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def _makerspace(self, request, makerspace_id):
        return get_object_or_404(
            rbac.scope_by_action(
                request.user,
                rbac.Action.MANAGE_MAKERSPACE,
                servable_queryset(),
                field="id",
            ),
            pk=makerspace_id,
        )

    @extend_schema(
        tags=["Admin payment settings"],
        summary="Retrieve makerspace payment settings",
        responses={
            200: MakerspacePaymentSettingsSerializer,
            401: PaymentSettingsErrorSerializer,
            403: OpenApiResponse(PaymentSettingsErrorSerializer, description="Permission denied."),
            404: PaymentSettingsErrorSerializer,
        },
    )
    def get(self, request, makerspace_id):
        makerspace = self._makerspace(request, makerspace_id)
        payment_settings = MakerspacePaymentSettings.for_makerspace(makerspace)
        return Response(MakerspacePaymentSettingsSerializer(
            payment_settings, context={"request": request},
        ).data)

    @extend_schema(
        tags=["Admin payment settings"],
        summary="Update makerspace payment settings",
        request=MakerspacePaymentSettingsSerializer,
        responses={
            200: MakerspacePaymentSettingsSerializer,
            400: OpenApiResponse(
                OpenApiTypes.OBJECT,
                description="Field errors, including credential changes blocked by live hosted or native collections.",
            ),
            401: PaymentSettingsErrorSerializer,
            403: OpenApiResponse(
                PaymentSettingsErrorSerializer,
                description="Permission denied, or recent_reauth_required for provider/credential writes.",
            ),
            404: PaymentSettingsErrorSerializer,
            409: OpenApiResponse(
                PaymentProviderConflictSerializer,
                description="payment_provider_conflict: settle or close pending collections on the other provider first.",
            ),
        },
    )
    def patch(self, request, makerspace_id):
        makerspace = self._makerspace(request, makerspace_id)
        if any(field in request.data for field in ("provider", *MAKERSPACE_CREDENTIAL_FIELDS)):
            # The provider and its credentials are the online rail; loan rules and the
            # currency on this row stay editable while `payments` is off (#95).
            if not module_enabled(makerspace, "payments"):
                raise module_off("payments")
            require_recent_reauth(request)
        # Preserve lazy default initialization even when the PATCH is invalid.
        # Requested changes and their audit entry still commit together below.
        payment_settings, _ = MakerspacePaymentSettings.objects.get_or_create(
            makerspace=makerspace
        )
        with transaction.atomic():
            serializer = MakerspacePaymentSettingsSerializer(
                payment_settings, data=request.data, partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            updated = serializer.save()
            audit.record(
                request.user,
                "payments.settings_updated",
                makerspace=makerspace,
                target=updated,
                meta={"fields": sorted(serializer.validated_data)},
            )
        return Response(MakerspacePaymentSettingsSerializer(
            updated, context={"request": request},
        ).data)


class StripeConnectOnboardingView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Admin payment settings"],
        summary="Start Stripe Connect onboarding",
        request=None,
        responses={
            200: StripeConnectOnboardingSerializer,
            403: PaymentSettingsErrorSerializer,
            404: PaymentSettingsErrorSerializer,
            503: PaymentSettingsErrorSerializer,
        },
    )
    def post(self, request, makerspace_id):
        if is_self_host():
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        makerspace = get_object_or_404(
            rbac.scope_by_action(
                request.user,
                rbac.Action.MANAGE_MAKERSPACE,
                servable_queryset(),
                field="id",
            ),
            pk=makerspace_id,
        )
        require_module(makerspace, "payments")
        try:
            authorize_url = create_onboarding(makerspace, request.user)
        except PaymentsUnavailable:
            return Response(
                {"detail": "Stripe Connect is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        audit.record(
            request.user,
            "payments.connect_onboarding_started",
            makerspace=makerspace,
            target=makerspace,
        )
        return Response({"authorize_url": authorize_url})
