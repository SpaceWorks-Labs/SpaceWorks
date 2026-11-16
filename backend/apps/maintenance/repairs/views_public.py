"""Account-less reporting (#80, #103) and the technician opt-in page (C-4).

In a space without member accounts the borrower (or guest booker) proves their email
with the same one-time code a borrow request uses (`.../requests/email-code`), and the
report is accepted only for a loan or booking filed under that proven address. The
opt-in page is reached only through the link staff sent; it shows the technician's
first-party name and the space, never their contact details.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.hardware_requests.throttles import AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.request_access import contact_requests_allowed
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS

from . import areas, optin, photos, services_issues as svc
from .serializers_actions import IssuePhotoUploadResponseSerializer, IssuePhotoUploadSerializer, PublicIssueReportCreateSerializer
from .serializers_contacts import TechnicianOptInAcceptSerializer, TechnicianOptInPageSerializer
from .serializers_issues import IssueReportCreatedSerializer
from .views_common import ERRORS
from .views_member import report_subject

TAGS = ["Public repairs"]
THROTTLES = [AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle]


class PublicIssuePhotoSerializer(IssuePhotoUploadSerializer):
    contact_email = serializers.EmailField(max_length=254)


def _space(slug):
    from django.http import Http404
    space = get_public_makerspace(slug)
    if not contact_requests_allowed(space):
        raise Http404()  # spaces with member accounts report from the member area
    if not areas.areas_on(space, areas.REPORTING):
        areas.refuse("issue reporting")
    return space


def _email_key(space, email):
    from apps.hardware_requests.contact_verification import email_key
    return email_key(space, email)


class PublicIssuePhotoUploadView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = THROTTLES

    @extend_schema(tags=TAGS, summary="Presign a private photo for an account-less report", auth=[{"jwtAuth": []}, {}],
                   parameters=PUBLIC_API_AUTH_PARAMETERS, request=PublicIssuePhotoSerializer,
                   responses={201: IssuePhotoUploadResponseSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = _space(makerspace_slug)
        body = PublicIssuePhotoSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        owner = photos.owner_for_email(_email_key(space, body.validated_data["contact_email"]))
        try:
            data = photos.issue_upload(space, body.validated_data["content_type"], owner)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(data, status=status.HTTP_201_CREATED)


class PublicIssueReportView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = THROTTLES

    @extend_schema(tags=TAGS, summary="Report a problem with my loan or booking (email-code verified)",
                   auth=[{"jwtAuth": []}, {}], parameters=PUBLIC_API_AUTH_PARAMETERS,
                   request=PublicIssueReportCreateSerializer, responses={201: IssueReportCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        from apps.hardware_requests.contact_verification import consume_code
        space = _space(makerspace_slug)
        body = PublicIssueReportCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        email = data["contact_email"]
        key = _email_key(space, email)
        # Prove the address FIRST, so an unproven caller learns nothing about whose loan is whose.
        consume_code(space, email, data["email_code"])
        source, origin, subject_type, subject = report_subject(space, data, email_key=key, email=email)
        validated = photos.validate(space, data["photos"], photos.owner_for_email(key))
        issue = svc.file_report(space, reporter=None, source=source, origin=origin, subject_type=subject_type,
                                subject=subject, title=data["title"], description=data["description"],
                                validated=validated, reporter_name=data["contact_name"], reporter_email=email)
        return Response({"id": issue.pk, "state": issue.state}, status=status.HTTP_201_CREATED)


class TechnicianOptInView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = THROTTLES

    @extend_schema(tags=TAGS, summary="What a technician's opt-in link is for", auth=[],
                   responses={200: TechnicianOptInPageSerializer, 404: OpenApiResponse(description="Invalid or expired.")})
    def get(self, request, token):
        contact = optin.contact_for_token(token)
        return Response({"makerspace_name": contact.makerspace.name, "technician_name": contact.name,
                         "has_phone": bool(contact.phone), "telegram_start": f"/start {token}",
                         "consent": {"email": True, "telegram": bool(contact.telegram_opted_in_at),
                                     "whatsapp": bool(contact.whatsapp_opted_in_at),
                                     "sms": bool(contact.sms_opted_in_at)}})

    @extend_schema(tags=TAGS, summary="Agree to repair requests by WhatsApp and/or SMS", auth=[],
                   request=TechnicianOptInAcceptSerializer,
                   responses={200: TechnicianOptInPageSerializer, 400: OpenApiResponse(description="Invalid."),
                              404: OpenApiResponse(description="Invalid or expired.")})
    def post(self, request, token):
        body = TechnicianOptInAcceptSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        optin.accept(token, body.validated_data["channels"])
        return self.get(request, token)
