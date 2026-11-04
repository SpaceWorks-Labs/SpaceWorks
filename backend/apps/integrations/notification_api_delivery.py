from dataclasses import asdict
from .notification_cutover import guarded, sending_allowed, CutoverClosed

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from .notification_api_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write
from .models_contract import NotificationDelivery
from .models_destinations import NotificationDestination
from .models_endpoints import ChannelConfiguration, NotificationEndpoint
from .notification_api_access import contract_space
from .notification_api_personal import ProofThrottle
from .notification_api_serializers import (
    ContractDeliverySerializer, ContractTestSerializer, DeliveryPageSerializer, ProviderResultSerializer,
)
from .notification_providers import ProviderResult, provider_for, safe_error
from .notification_resolution import policy_rows


class ContractDeliveryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notification contract"], parameters=[OpenApiParameter("page", int)],
                   responses={200: DeliveryPageSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id)
        rows = policy_rows(NotificationDelivery, space).select_related("envelope")
        if not rbac.is_space_manager_identity(request.user, space.pk):
            rows = rows.filter(envelope__recipient=request.user)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows.order_by("-created_at", "-pk"), request, view=self)
        return paginator.get_paginated_response(ContractDeliverySerializer(page, many=True).data)


class ContractTestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProofThrottle]

    @extend_schema(tags=["Notification contract"], request=ContractTestSerializer,
                   responses={200: ProviderResultSerializer, **errors(400, 401, 403, 404, 429, 423, 503)})
    @guarded(mutation=True)
    def post(self, request, makerspace_id):
        if not sending_allowed():
            raise CutoverClosed()
        space = contract_space(request.user, makerspace_id, manager=True)
        serializer = ContractTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["channel"] in {"sms", "whatsapp"}:
            if data["channel"] == "whatsapp":
                get_object_or_404(policy_rows(NotificationEndpoint, space), pk=data["endpoint_id"],
                    user=request.user, channel="whatsapp", verification_state="verified", revoked_at=None)
            from .notification_diagnostics import queue
            row, _ = queue(space, request.user, data["channel"],
                feature=data.get("feature", "hardware_requests"), event=data.get("event", "accepted"))
            from .notification_delivery import send
            if row:
                send(row.pk)
                row.refresh_from_db()
            result = ProviderResult(bool(row and row.state in {"accepted", "sent", "delivered", "read"}),
                provider_id=row.provider_id if row else "", error_code=row.last_error if row else "not_configured")
            return Response(ProviderResultSerializer(asdict(result)).data)
        config = get_object_or_404(policy_rows(ChannelConfiguration, space), channel=data["channel"], enabled=True)
        if data.get("endpoint_id"):
            target = get_object_or_404(policy_rows(NotificationEndpoint, space), pk=data["endpoint_id"],
                user=request.user, configuration=config, integration_generation=config.generation,
                verification_state="verified", revoked_at=None)
            if not config.personal_enabled:
                raise ValidationError({"channel": "Personal delivery is disabled."})
        else:
            if not config.room_enabled:
                raise ValidationError({"channel": "Room delivery is disabled."})
            target = get_object_or_404(policy_rows(NotificationDestination, space), pk=data["room_id"],
                                      channel=config.channel, is_active=True)
        provider = provider_for(config)
        try:
            result = provider.test(target) if provider else ProviderResult(False, error_code="not_configured")
        except Exception:
            result = ProviderResult(False, error_code="provider_error")
        with tenant_write(space.pk):
            audit.record(request.user, "notification.channel_tested", makerspace=space, target=config,
                         meta={"channel": config.channel, "accepted": result.accepted})
        response = asdict(result)
        response["sanitized_error"] = "" if result.accepted else safe_error(result)
        response["error_code"] = "" if result.accepted else safe_error(result)
        return Response(ProviderResultSerializer(response).data)
