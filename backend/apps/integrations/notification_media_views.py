"""Public provider fetch; possession never bypasses the live payer policy."""
import logging

from django.http import HttpResponse
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from .notification_media import consume_grant

logger = logging.getLogger(__name__)


class MediaFetchThrottle(AnonRateThrottle):
    scope = "notification_media"
    rate = "60/min"


class NotificationMediaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [MediaFetchThrottle]
    http_method_names = ["get", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(tags=["Notification contract"], auth=[], request=None,
        summary="Consume a single-use provider document grant",
        description="Live payer, endpoint consent, installation, preferences and tenant write gates are checked. "
                    "HEAD returns 405 without consuming. All responses are private and no-store.",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY,
                   404: OpenApiResponse(ErrorSerializer), 405: OpenApiResponse(ErrorSerializer),
                   429: OpenApiResponse(ErrorSerializer)})
    def get(self, request, token):
        try:
            result = consume_grant(token)
        except Exception as exc:
            # Never log the URL/bearer or an external exception's message.
            logger.warning("notification_media_fetch_failed", extra={"failure_type": type(exc).__name__})
            result = None
        if result is None:
            return Response({"detail": "Document unavailable.", "code": "not_found"}, status=404)
        filename, pdf = result
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = content_disposition_header(True, filename)
        return response
