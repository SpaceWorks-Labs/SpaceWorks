"""Anonymous hosting-request routes on a managed platform.

Built like ``PublicInvitationRequestView``: AllowAny with DEFAULT authentication (so
the claim-session authenticator runs and refuses claim sessions), a scoped throttle,
and the availability gate as the first statement. Submissions always answer the same
202 -- honeypot, per-address overflow and a real submission are indistinguishable --
and token routes 404 on every non-match, so nothing here reveals whether an address
or a request exists. No route takes an email as a lookup key.
"""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.hardware_requests.public_request_views import _honeypot_filled
from apps.hosting_requests import workflow
from apps.hosting_requests.availability import require_public_available
from apps.hosting_requests.serializers import (
    ACK,
    HostingAckSerializer,
    HostingInvitationPreviewSerializer,
    HostingInvitationSubmitSerializer,
    HostingRequestStatusSerializer,
    HostingRequestSubmitSerializer,
    HostingTokenSerializer,
)
from apps.hosting_requests.throttles import HostingRequestEmailThrottle
from apps.openapi_errors import errors

logger = logging.getLogger(__name__)
TAGS = ["Hosting requests"]
SUBMIT_ERRORS = errors(400, 404, 429, 503, e404="Hosting requests are not available here.")
TOKEN_ERRORS = errors(400, 404, 429, 503, e404="Unknown, expired or no longer available link.")


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _ack():
    return _no_store(Response(ACK, status=status.HTTP_202_ACCEPTED))


def _email_budget_left(request, view):
    if HostingRequestEmailThrottle().allow_request(request, view):
        return True
    from apps.accounts.audit_events import fingerprint

    email = str(request.data.get("applicant_email") or "")
    logger.info("hosting_request_email_throttled", extra={"email_fingerprint": fingerprint(email)})
    return False


class HostingRequestSubmitView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hosting_request_submit"

    @extend_schema(
        tags=TAGS, auth=[], summary="Ask to host a makerspace on this platform",
        description="Always answers 202 with the same body. A confirmation link is emailed; "
                    "the request reaches review only after the address is confirmed.",
        request=HostingRequestSubmitSerializer,
        responses={202: HostingAckSerializer, **SUBMIT_ERRORS},
    )
    def post(self, request):
        require_public_available()
        if _honeypot_filled(request.data):
            return _ack()
        serializer = HostingRequestSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if _email_budget_left(request, self):
            workflow.create_public(serializer.validated_data)
        return _ack()


class HostingRequestOpenView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hosting_request_token"

    @extend_schema(
        tags=TAGS, auth=[], summary="Confirm a hosting request and read its status",
        description="The first call with a fresh link confirms the email address and sends "
                    "the request to review; later calls only read its status.",
        request=HostingTokenSerializer,
        responses={200: HostingRequestStatusSerializer, **TOKEN_ERRORS},
    )
    def post(self, request):
        require_public_available()
        serializer = HostingTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = workflow.open_by_token(serializer.validated_data["token"])
        return _no_store(Response(HostingRequestStatusSerializer(row).data))


class HostingInvitationResolveView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hosting_request_token"

    @extend_schema(
        tags=TAGS, auth=[], summary="Preview a hosting invitation",
        request=HostingTokenSerializer,
        responses={200: HostingInvitationPreviewSerializer, **TOKEN_ERRORS},
    )
    def post(self, request):
        require_public_available()
        serializer = HostingTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = workflow.resolve_invitation(serializer.validated_data["token"])
        inviter = row.inviter_organization if row.inviter_kind == "organization" else row.inviter_makerspace
        join = row.inviter_organization if workflow.join_available(row) else None
        payload = {
            "inviter_name": getattr(inviter, "name", "") or "A Space Works community",
            "join_organization_name": join.name if join is not None else None,
            "space_name": row.space_name,
            "applicant_email": row.applicant_email,
            "invite_note": row.invite_note,
            "expires_at": row.invite_expires_at,
        }
        return _no_store(Response(HostingInvitationPreviewSerializer(payload).data))


class HostingInvitationSubmitView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hosting_request_submit"

    @extend_schema(
        tags=TAGS, auth=[], summary="Answer a hosting invitation",
        description="Replaces any earlier answer and emails a fresh confirmation link.",
        request=HostingInvitationSubmitSerializer,
        responses={202: HostingAckSerializer, **SUBMIT_ERRORS},
    )
    def post(self, request):
        require_public_available()
        if _honeypot_filled(request.data):
            return _ack()
        serializer = HostingInvitationSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        token = data.pop("token")
        if _email_budget_left(request, self):
            workflow.submit_invited(token, data)
        return _ack()
