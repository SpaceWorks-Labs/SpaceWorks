from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.events.models_certificates import EventAttendanceCertificate
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from .models import EventCertificatePublicationPolicy
from zoneinfo import ZoneInfo


class VerificationSerializer(serializers.Serializer):
    event = serializers.CharField()
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=("valid", "revoked"))


class VerifyThrottle(AnonRateThrottle):
    rate = "30/min"


def project(verification_id, request=None):
    row = EventAttendanceCertificate.objects.filter(serial=verification_id, public_verification_enabled=True,
                                                    status__in=("active", "revoked")).select_related("event__makerspace").first()
    if (not row or not is_servable(row.event.makerspace) or not module_enabled(row.event.makerspace, "events")
            or not EventCertificatePublicationPolicy.objects.filter(event=row.event, enabled=True).exists()):
        raise NotFound()
    if request:
        from apps.makerspaces.public_profile_access import _request_tenant_ids
        if any(pk != row.event.makerspace_id for pk in _request_tenant_ids(request)):
            raise NotFound()
    return {"event": row.event_title, "date": row.event_starts_at.astimezone(ZoneInfo(row.event_timezone_name)).date(),
            "status": "valid" if row.status == "active" else "revoked"}


class CertificateVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [VerifyThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @extend_schema(tags=["Event certificates"], responses={200: VerificationSerializer, 404: ErrorSerializer, 429: ErrorSerializer},
                   description="Explicitly published event/date/status only, including revoked certificates. No identity or PDF access.")
    def get(self, request, verification_id):
        response = Response(VerificationSerializer(project(verification_id, request)).data)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
