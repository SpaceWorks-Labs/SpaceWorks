from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.boxes.models import Box, QrCode
from apps.boxes.access import inventory_qr_codes
from apps.boxes.qr_lookup import scanned_or_404
from apps.hardware_requests.direct_loan_serializers import DirectLoanItemSerializer
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.kit_checklists import issue_expectations, return_expectations
from apps.hardware_requests.kit_preview import preview_targets
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.hardware_requests.return_helpers import build_resolutions, remaining_quantity
from apps.hardware_requests.serializers import IssueRejectSerializer, ReturnItemResolutionSerializer
from apps.inventory.kit_serializers import KitPreviewSerializer
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace
from apps.hardware_requests.kit_contact_preview import ContactKitPreviewInputSerializer, contact_kit_rows
from apps.hardware_requests.self_checkout_contact import contact_mode
from apps.hardware_requests.self_checkout_views import _public_tool_makerspace
from apps.hardware_requests.throttles import AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle
from apps.presence.guest_guard import require_member_or_guest
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 429)}


class KitPreviewInputSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=["issue", "return"], default="issue")
    request_id = serializers.IntegerField(min_value=1, required=False)
    loan_id = serializers.IntegerField(min_value=1, required=False)
    box_code = serializers.CharField(required=False, allow_blank=True)
    container_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    qr_payloads = serializers.ListField(child=serializers.CharField(max_length=64), max_length=50, required=False)
    items = DirectLoanItemSerializer(many=True, required=False, max_length=20)
    rejects = IssueRejectSerializer(many=True, required=False, max_length=20)
    resolutions = ReturnItemResolutionSerializer(many=True, required=False, max_length=70)

    def validate(self, attrs):
        if attrs.get("request_id") and attrs.get("loan_id"):
            raise serializers.ValidationError(gettext("Provide one request or loan reference."))
        if attrs.get("loan_id") and attrs["phase"] != "return":
            raise serializers.ValidationError(gettext("A loan reference is for return previews."))
        if attrs["phase"] == "return" and not (attrs.get("request_id") or attrs.get("loan_id")):
            raise serializers.ValidationError(gettext("A return preview requires a request or loan reference."))
        for field in ("rejects", "resolutions"):
            ids = [row["item_id"] for row in attrs.get(field, [])]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({field: gettext("Item references must be unique.")})
        return attrs


def _full_resolutions(request):
    return [{"item": item, "returned": remaining_quantity(item), "damaged": 0, "missing": 0}
            for item in request.items.all() if remaining_quantity(item) > 0]


class StaffKitPreviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin requests"], summary="Preview required issue or return kit components",
                   request=KitPreviewInputSerializer, responses={200: KitPreviewSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        serializer = KitPreviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = rbac.Action.RETURN_REQUEST if data["phase"] == "return" else (
            rbac.Action.ISSUE_REQUEST if data.get("request_id") else rbac.Action.ISSUE_DIRECT_LOAN)
        space = get_object_or_404(rbac.scope_by_action(request.user, action, Makerspace.objects.all(), field="id"), pk=makerspace_id)
        require_action(request.user, action, space.pk)
        require_module(space, "request_workflow")
        if data.get("loan_id") or not data.get("request_id"):
            require_feature(space, "inventory.self_checkout")
        if data.get("container_id"):
            require_module(space, "containers")
        if data.get("loan_id"):
            loan = get_object_or_404(rbac.scope_by_action(request.user, action, PublicToolLoan.objects.all()),
                                   pk=data["loan_id"], makerspace=space, source=PublicToolLoan.Source.ADMIN_DIRECT)
            rows = return_expectations(loan.request, _full_resolutions(loan.request))
        elif data.get("request_id"):
            hardware = get_object_or_404(rbac.scope_by_action(request.user, action, HardwareRequest.objects.all()),
                                       pk=data["request_id"], makerspace=space)
            if data["phase"] == "return":
                resolved = build_resolutions(hardware, data["resolutions"]) if data.get("resolutions") else []
                rows = return_expectations(hardware, resolved)
            else:
                box = hardware.assigned_box
                if data.get("box_code"):
                    box = get_object_or_404(rbac.scope_by_action(request.user, action, Box.objects.all()),
                                           code=data["box_code"], makerspace=space, is_active=True)
                rows = issue_expectations(hardware, box, data.get("rejects"))
        else:
            rows = preview_targets(request.user, space, items=data.get("items", []),
                qr_payloads=data.get("qr_payloads", []), container_id=data.get("container_id"))
        return Response(KitPreviewSerializer({"components": rows}).data)


class MemberKitPreviewInputSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=64)
    phase = serializers.ChoiceField(choices=["issue", "return"])


class MemberKitPreviewView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MemberPrincipalRateThrottle, AnonymousRequestIpBurstThrottle, AnonymousRequestIpHourThrottle]
    throttle_scope = "public_tool_checkout"

    @extend_schema(tags=["Public requests"], summary="Preview kit components for a scanned self-checkout tool",
                   description=("Signed-in member where the makerspace has member accounts. Without them "
                                "(`request_access: contact`) send `contact_email` and the `email_code`; the "
                                "code is checked, not spent (#104)."),
                   auth=[{"jwtAuth": []}, {}],
                   request=MemberKitPreviewInputSerializer, parameters=PUBLIC_API_AUTH_PARAMETERS,
                   responses={200: KitPreviewSerializer, **ERRORS})
    def post(self, request, makerspace_slug):
        space = _public_tool_makerspace(makerspace_slug)
        require_feature(space, "inventory.self_checkout")
        if contact_mode(request, space, taking=str(request.data.get("phase", "")) == "issue"):
            serializer = ContactKitPreviewInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            rows = contact_kit_rows(space, serializer.validated_data)
            return Response(KitPreviewSerializer({"components": rows}).data)
        require_member_or_guest(request.user, space)  # decision 223: a live guest pass is admitted too
        serializer = MemberKitPreviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["phase"] == "issue":
            rows = preview_targets(request.user, space, qr_payloads=[data["payload"]], public=True)
        else:
            qr = scanned_or_404(rbac.scope_by_makerspace(request.user, inventory_qr_codes(
                QrCode.objects.filter(makerspace=space, status=QrCode.Status.ACTIVE))), data["payload"])
            loan = get_object_or_404(rbac.scope_by_makerspace(request.user, PublicToolLoan.objects.all()),
                                     qr_code=qr, makerspace=space, requester=request.user,
                                     source=PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT, status=PublicToolLoan.Status.CHECKED_OUT)
            rows = return_expectations(loan.request, _full_resolutions(loan.request))
        return Response(KitPreviewSerializer({"components": rows}).data)
