from zoneinfo import ZoneInfo

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
from .output_serializers import VerificationSerializer

NOTES = {"attendance_corrected": "It was withdrawn after the organisers corrected their records.",
         "event_cancelled": "It was withdrawn because the event was cancelled.",
         "staff_revoked": "It was withdrawn by the organisers."}


class VerifyThrottle(AnonRateThrottle):
    rate = "30/min"


def project(verification_id, request=None):
    """The public view of one certificate: issuer, event, date, kind, status, the PDF fingerprint,
    and the holder's name only when they chose to show it."""
    row = verified_row(verification_id, request)
    from .merge import frozen_merge, kind_title
    valid = row.status == "active"
    note = (f"This certificate is valid. It was issued by {row.issuer_name}." if valid
            else "This certificate is no longer valid. " + NOTES.get(row.revocation_reason, NOTES["staff_revoked"]))
    return {"event": row.event_title, "date": row.event_starts_at.astimezone(ZoneInfo(row.event_timezone_name)).date(),
            "status": "valid" if valid else "revoked", "issuer": row.issuer_name, "kind": row.kind,
            "kind_title": kind_title(row.kind), "award": frozen_merge(row).get("award", ""),
            # A revoked certificate no longer vouches for anyone, so it never names its holder.
            "recipient_name": row.recipient_name if row.holder_name_public and valid else None,
            "status_note": note, "serial": row.serial, "sha256": row.sha256}


def verified_row(verification_id, request=None):
    row = EventAttendanceCertificate.objects.filter(serial=verification_id, public_verification_enabled=True,
                                                    status__in=("active", "revoked")).select_related("event__makerspace").first()
    if (not row or not is_servable(row.event.makerspace) or not module_enabled(row.event.makerspace, "events")
            or not EventCertificatePublicationPolicy.objects.filter(event=row.event, enabled=True).exists()):
        raise NotFound()
    if request:
        from apps.makerspaces.public_profile_access import _request_tenant_ids
        if any(pk != row.event.makerspace_id for pk in _request_tenant_ids(request)):
            raise NotFound()
    return row


class CertificateVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [VerifyThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Robots-Tag"] = "noindex"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(tags=["Event certificates"], responses={200: VerificationSerializer, 404: ErrorSerializer, 429: ErrorSerializer},
                   description="Explicitly published certificates only, including revoked ones: issuer, event, date, kind, "
                               "award, status, the issued PDF's SHA-256 and the holder's name only if they chose to show it. "
                               "No PDF access; unknown, private and pending IDs share one 404.")
    def get(self, request, verification_id):
        response = Response(VerificationSerializer(project(verification_id, request)).data)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
