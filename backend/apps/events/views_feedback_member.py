from django.utils.translation import gettext
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.events.certificate_storage import CertificateStorageUnavailable
from apps.events.member_history import registrations_for_space
from apps.events.models import EventAttendanceCertificate, EventFeedbackSurvey
from apps.events.serializers_feedback import (
    CertificateDownloadSerializer,
    FeedbackFormSerializer,
    FeedbackSubmissionResponseSerializer,
    FeedbackSubmissionSerializer,
)
from apps.events.services_certificates import download_url
from apps.events.views_feedback_public import feedback_form_payload
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_service import active_membership
from apps.presence.guard import require_active_member


ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid feedback answers."),
    403: OpenApiResponse(ErrorSerializer, description="Active membership is required."),
    404: OpenApiResponse(ErrorSerializer, description="Feedback resource not found."),
    409: OpenApiResponse(ErrorSerializer, description="Feedback or certificate state conflict."),
    429: OpenApiResponse(ErrorSerializer, description="Rate limit exceeded."),
}


def _owned_registration(request, makerspace_id, pk):
    membership = active_membership(request.user, makerspace_id)
    if membership is None:
        # Account-only attendee (open item B10): the ticket they hold authorizes its own row only; a
        # revoked membership is refused inside `participant_space`, never downgraded to account-only.
        from apps.events.models import EventRegistration
        from apps.events.participant_access import participant_space
        space = participant_space(request.user, makerspace_id, pk)
        registration = EventRegistration.objects.select_related("event__makerspace", "registered_via_makerspace").filter(
            member=request.user, event__makerspace=space, pk=pk).first()
        if registration is None:
            raise NotFound()
        return registration
    require_module(membership.makerspace, "events")
    require_active_member(request.user, membership.makerspace)
    registration = registrations_for_space(membership.makerspace, request.user).select_related(
        "event__makerspace", "registered_via_makerspace",
    ).filter(pk=pk).first()
    if registration is None:
        raise NotFound()
    return registration


def _survey_for_registration(registration, *, allow_existing=False):
    survey = EventFeedbackSurvey.objects.filter(event=registration.event).first()
    if survey is None or timezone.now() < registration.event.ends_at:
        raise NotFound()
    existing = registration.feedback_responses.order_by("-created_at", "-id").first()
    if not survey.is_open and not (allow_existing and existing is not None):
        raise NotFound()
    certificate = None if existing is None else existing.certificates.order_by("-revision").first()
    return survey, certificate


class MemberEventFeedbackView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "event_register"

    @extend_schema(tags=["Member events"], responses={200: FeedbackFormSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        registration = _owned_registration(request, makerspace_id, pk)
        survey, certificate = _survey_for_registration(registration, allow_existing=True)
        payload = feedback_form_payload(registration.event, survey, certificate=certificate)
        return Response(FeedbackFormSerializer(payload).data)

    @extend_schema(tags=["Member events"], request=FeedbackSubmissionSerializer, responses={201: FeedbackSubmissionResponseSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        registration = _owned_registration(request, makerspace_id, pk)
        survey, _certificate = _survey_for_registration(registration)
        serializer = FeedbackSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.events.feedback_modes import submit
        _response, certificate = submit(registration.event, survey, user=request.user,
                                        data=serializer.validated_data, registration=registration)
        payload = {"thank_you_text": survey.thank_you_text, "certificate": certificate}
        return Response(FeedbackSubmissionResponseSerializer(payload).data, status=201)


class MemberEventCertificateDownloadView(APIView):
    permission_classes = [IsAuthenticated]
    from apps.events.throttles import CredentialRenderThrottle
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Member events"], description="Private audited certificate download; configurable renders are bounded to 30/hour per account.", responses={200: CertificateDownloadSerializer, 429: ErrorSerializer, 410: OpenApiResponse(ErrorSerializer, description="Certificate revoked."), 503: OpenApiResponse(ErrorSerializer, description="Certificate storage unavailable."), **ERRORS})
    def get(self, request, makerspace_id, pk):
        from .certificates.owner_queries import owner_certificate
        certificate = owner_certificate(request.user, makerspace_id, pk)
        if certificate.status == EventAttendanceCertificate.Status.REVOKED:
            return Response({"detail": gettext("Certificate revoked."), "code": "certificate_revoked"}, status=status.HTTP_410_GONE)
        try:
            certificate, url = download_url(certificate, actor=request.user)
        except CertificateStorageUnavailable:
            return Response({"detail": gettext("Certificate storage is unavailable."), "code": "storage_unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"url": url, "expires_at": timezone.now() + timedelta(seconds=settings.EVIDENCE_URL_TTL_SECONDS)})
