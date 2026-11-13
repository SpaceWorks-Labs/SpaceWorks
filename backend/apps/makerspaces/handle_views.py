"""Public username availability check + suggestion (decision 308). Advisory; the claim re-checks under lock."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle

from .handle_gate import HandleCheckSerializer
from .public_profile_handles import check_handle, suggest_handle
from .throttles import HANDLE_CHECK_THROTTLES


class HandleCheckResponse(serializers.Serializer):
    handle = serializers.CharField(allow_null=True)
    available = serializers.BooleanField(allow_null=True)
    reason = serializers.ChoiceField(choices=["", "invalid", "reserved", "taken"])
    suggestion = serializers.CharField(allow_null=True)


class HandleCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle, *HANDLE_CHECK_THROTTLES]
    throttle_scope = "public_read"

    @extend_schema(
        tags=["Auth"], auth=[], summary="Check a username and get the best suggestion",
        parameters=[OpenApiParameter("handle", str), OpenApiParameter("username", str), OpenApiParameter("display_name", str)],
        responses={200: HandleCheckResponse, 429: OpenApiResponse(description="Request rate exceeded.")},
    )
    def get(self, request):
        data = HandleCheckSerializer(data=request.query_params)
        data.is_valid(raise_exception=True)
        value = data.validated_data.get("handle", "")
        available, reason = check_handle(value) if value else (None, "")
        suggestion = suggest_handle(username=data.validated_data.get("username", ""),
                                    display_name=data.validated_data.get("display_name", ""))
        response = Response(HandleCheckResponse({
            "handle": value.lower() or None, "available": available, "reason": reason, "suggestion": suggestion}).data)
        response["Cache-Control"] = "no-store"
        return response
