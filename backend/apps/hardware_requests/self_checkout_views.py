from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests import self_checkout_contact as contact_flow
from apps.hardware_requests import self_checkout_workflow
from apps.hardware_requests.self_checkout_serializers import (
    ContactEvidenceUrlRequestSerializer,
    ContactToolCheckoutSerializer,
    ContactToolScanSerializer,
    PublicToolCheckoutSerializer,
    PublicToolEvidenceUrlRequestSerializer,
    PublicToolEvidenceUrlResponseSerializer,
    PublicToolLoanSerializer,
    PublicToolScanSerializer,
)
from apps.hardware_requests.throttles import AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.makerspaces.editions import require_public_surface
from apps.makerspaces.guards import require_feature
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.openapi import (
    PUBLIC_API_AUTH_PARAMETERS,
    PUBLIC_TOOL_CHECKOUT_EXAMPLE,
    PUBLIC_TOOL_SCAN_EXAMPLE,
)
from apps.presence.guard import require_active_member_presence

CONTACT_NOTE = (
    "Signed-in member account where the makerspace has member accounts. Without them "
    "(bootstrap `request_access: contact`) everyone sends `contact_name`, `contact_phone`, "
    "`contact_email` and an `email_code` from `requests/email-code`, plus the "
    "`evidence_grant` the upload URL returned; evidence rules are unchanged (#91)."
)


class _PublicToolView(APIView):
    """Account-less calls are admitted only where the space has no member accounts
    (`self_checkout_contact.contact_mode`); everywhere else a signed-in account is needed."""

    permission_classes = [AllowAny]
    throttle_classes = [MemberPrincipalRateThrottle, AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle]


class PublicToolEvidenceUploadUrlView(_PublicToolView):
    throttle_scope = "public_tool_checkout"

    @extend_schema(
        tags=["Public requests"],
        summary="Create a public self-checkout evidence upload URL",
        description=CONTACT_NOTE,
        auth=[{"jwtAuth": []}, {}],
        parameters=PUBLIC_API_AUTH_PARAMETERS,
        request=PublicToolEvidenceUrlRequestSerializer,
        responses={201: PublicToolEvidenceUrlResponseSerializer, **PUBLIC_ERROR_RESPONSES},
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = _public_tool_makerspace(makerspace_slug)
        require_feature(makerspace, "inventory.self_checkout")
        taking = str(request.data.get("evidence_type", "")) == EvidencePhoto.EvidenceType.ISSUE
        if contact_flow.contact_mode(request, makerspace, taking=taking):
            serializer = ContactEvidenceUrlRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            return contact_flow.issue_upload(
                makerspace, data, uploader=contact_flow.principal(makerspace), actor=None,
                contact_email=data["contact_email"],
            )
        presence = require_active_member_presence(request.user, makerspace)
        serializer = PublicToolEvidenceUrlRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["evidence_type"] == EvidencePhoto.EvidenceType.ISSUE:
            # Issue evidence is the first step of taking a tool; return evidence never is.
            require_current_term(makerspace, presence.membership)
        return contact_flow.issue_upload(makerspace, data, uploader=request.user, actor=request.user)


class PublicToolCheckoutView(_PublicToolView):
    throttle_scope = "public_tool_checkout"

    @extend_schema(
        tags=["Public requests"],
        summary="Check out a public tool by QR",
        description=CONTACT_NOTE,
        auth=[{"jwtAuth": []}, {}],
        parameters=PUBLIC_API_AUTH_PARAMETERS,
        request=PublicToolCheckoutSerializer,
        responses={201: PublicToolLoanSerializer, **PUBLIC_ERROR_RESPONSES},
        examples=[PUBLIC_TOOL_CHECKOUT_EXAMPLE],
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = _public_tool_makerspace(makerspace_slug)
        require_feature(makerspace, "inventory.self_checkout")
        contact = contact_flow.contact_mode(request, makerspace, taking=True)
        if not contact:
            # Checking out is borrowing, so the optional lapsed-term rule applies exactly
            # as it does to a reviewed request. Returning a tool is never gated by it.
            require_current_term(
                makerspace, require_active_member_presence(request.user, makerspace).membership
            )
        serializer = (ContactToolCheckoutSerializer if contact else PublicToolCheckoutSerializer)(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        identity = contact_flow.confirmed_identity(makerspace, data) if contact else None
        loan = self_checkout_workflow.checkout_tool(
            makerspace,
            identity.principal if identity else request.user,
            data["payload"],
            evidence_id=data["evidence_id"],
            remark=data.get("remark", ""),
            kit_checklist=data["kit_checklist"],
            contact=identity,
        )
        return Response(PublicToolLoanSerializer(loan).data, status=status.HTTP_201_CREATED)


class PublicToolReturnView(_PublicToolView):
    throttle_scope = "public_tool_return"

    @extend_schema(
        tags=["Public requests"],
        summary="Return a public tool by QR",
        description=CONTACT_NOTE,
        auth=[{"jwtAuth": []}, {}],
        parameters=PUBLIC_API_AUTH_PARAMETERS,
        request=PublicToolScanSerializer,
        responses={200: PublicToolLoanSerializer, **PUBLIC_ERROR_RESPONSES},
        examples=[PUBLIC_TOOL_SCAN_EXAMPLE],
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = _public_tool_makerspace(makerspace_slug)
        require_feature(makerspace, "inventory.self_checkout")
        contact = contact_flow.contact_mode(request, makerspace)
        if not contact:
            require_active_member_presence(request.user, makerspace)
        serializer = (ContactToolScanSerializer if contact else PublicToolScanSerializer)(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        identity = contact_flow.confirmed_identity(makerspace, data) if contact else None
        loan = self_checkout_workflow.return_tool(
            makerspace,
            identity.principal if identity else request.user,
            data["payload"],
            evidence_id=data["evidence_id"],
            remark=data["remark"],
            report_problem=data["report_problem"],
            problem_note=data["problem_note"],
            kit_checklist=data["kit_checklist"],
            contact=identity,
        )
        return Response(PublicToolLoanSerializer(loan).data)


def _require_module(makerspace, module_key):
    if not module_enabled(makerspace, module_key):
        from apps.makerspaces.guards import module_off
        raise module_off(module_key)


def _public_tool_makerspace(makerspace_slug):
    """The public tool routes are LOAN routes: an edition that hides the loan spine
    (`events`, `bookings`) makes them answer 404, like the catalogue and the request form.
    """
    require_public_surface("request_workflow")
    return get_public_makerspace(makerspace_slug)
