"""Internal cron transport. Never mount this URLconf under the full profile."""
import json

from django.conf import settings
from django.http import Http404
from django.utils.crypto import constant_time_compare
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiResponse, PolymorphicProxySerializer, extend_schema
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tick_policy import TickRateExceeded, consume_rate, free_profile
from .tick_service import run_tick

MAX_TICK_BODY_BYTES = 1024


def empty_tick_body(request):
    """Allow no body or a small JSON object with no caller-controlled fields."""
    if request.META.get("HTTP_TRANSFER_ENCODING"):
        return False
    try:
        raw_length = request.META.get("CONTENT_LENGTH") or "0"
        if raw_length != "0" and (not raw_length.isascii() or not raw_length.isdecimal() or raw_length.startswith("0")):
            return False
        length = int(raw_length)
        if not 0 <= length <= MAX_TICK_BODY_BYTES:
            return False
        body = request.body
        if len(body) != length:
            return False
        if not body:
            return True
        return request.content_type == "application/json" and json.loads(body) == {}
    except (ValueError, UnicodeError, OSError):
        return False


class TickSecretAuthentication(BaseAuthentication):
    def authenticate(self, request):
        provided = request.headers.get("X-Cron-Secret", "")
        if (not provided.isascii() or not request.is_secure()
                or request.headers.get("Origin") or request.headers.get("Sec-Fetch-Site")
                or request.headers.get("Authorization") or request.query_params
                or not constant_time_compare(provided, settings.FREE_TICK_SECRET)
                or not empty_tick_body(request)):
            raise PermissionDenied("Invalid cron request.")
        consume_rate(authenticated=True)
        return None


class TickSecretScheme(OpenApiAuthenticationExtension):
    target_class = TickSecretAuthentication
    name = "freeTickSecret"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "header", "name": "X-Cron-Secret"}


class TickResponseSerializer(serializers.Serializer):
    run_id = serializers.UUIDField()
    elapsed_seconds = serializers.FloatField()
    completed = serializers.IntegerField(min_value=0)
    deferred = serializers.IntegerField(min_value=0)
    failed = serializers.IntegerField(min_value=0)
    reasons = serializers.DictField(child=serializers.IntegerField(min_value=0))


class TickErrorSerializer(serializers.Serializer):
    code = serializers.CharField()


class FreeTickView(APIView):
    authentication_classes = (TickSecretAuthentication,)
    permission_classes = (AllowAny,)
    # The PostgreSQL counters below are the authoritative rate limits. No DRF
    # cache throttle is used as either the task lock or a permissive fallback.
    http_method_names = ("post",)

    def initial(self, request, *args, **kwargs):
        if not free_profile() or not getattr(settings, "FREE_TICK_SECRET", ""):
            raise Http404()
        consume_rate(authenticated=False)
        if request.method != "POST":
            self.method_not_allowed(request)
        super().initial(request, *args, **kwargs)

    def handle_exception(self, exc):
        if isinstance(exc, Http404):
            return Response({"code": "not_found"}, status=404)
        if isinstance(exc, PermissionDenied):
            return Response({"code": "forbidden"}, status=403)
        if isinstance(exc, TickRateExceeded):
            return Response({"code": "rate_limited"}, status=429, headers={"Retry-After": str(exc.seconds)})
        from rest_framework.exceptions import MethodNotAllowed
        if isinstance(exc, MethodNotAllowed):
            return Response({"code": "method_not_allowed"}, status=405, headers={"Allow": "POST"})
        # Do not disclose SQL, driver messages, DSNs, credentials or adapter text.
        return Response({"code": "tick_unavailable"}, status=503)

    @extend_schema(
        tags=["Internal"], extensions={"x-internal": True},
        request={"application/json": {"type": "object", "additionalProperties": False, "maxProperties": 0}},
        description="Free only. Accepts no body or an empty JSON object (maximum 1024 bytes).",
        responses={
            200: TickResponseSerializer,
            403: OpenApiResponse(TickErrorSerializer, description="Invalid cron request."),
            404: OpenApiResponse(TickErrorSerializer, description="Free tick is not configured."),
            405: OpenApiResponse(TickErrorSerializer, description="POST required."),
            429: OpenApiResponse(TickErrorSerializer, description="Atomic rate limit; observe Retry-After."),
            503: OpenApiResponse(
                PolymorphicProxySerializer(
                    component_name="FreeTickUnavailable",
                    serializers=[TickErrorSerializer, TickResponseSerializer],
                    resource_type_field_name=None,
                ),
                description="Admission, coordination or task failure; retry next tick.",
            ),
        },
    )
    def post(self, request):
        payload, status = run_tick()
        return Response(payload, status=status)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
