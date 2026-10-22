import uuid
from types import SimpleNamespace

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.hardware_requests import workflow
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.request_workflow import RequesterSnapshot
from apps.hardware_requests.serializers import (
    RequestSubmitResponseSerializer,
    RequestSubmitSerializer,
)
from apps.hardware_requests.view_helpers import (
    PUBLIC_ERROR_RESPONSES,
)
from apps.inventory.models import InventoryProduct
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.guards import require_feature
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.presence.guard import require_active_account, require_active_member_presence
from apps.openapi import (
    PUBLIC_API_AUTH_PARAMETERS,
    PUBLIC_REQUEST_SUBMIT_EXAMPLE,
)


class RequestSubmitView(APIView):
    """Submit a borrow request as the signed-in account (owner decision #75f).

    Every request needs an account: the account-less opt-in was removed, so the requester
    is always ``request.user`` and the contact snapshot is always account-derived. Requests
    filed before the removal keep their principal and unverified-contact snapshot, and stay
    readable through every staff and report surface.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(
        tags=["Public requests"],
        summary="Submit public borrow request",
        auth=[{"jwtAuth": []}],
        parameters=PUBLIC_API_AUTH_PARAMETERS,
        request=RequestSubmitSerializer,
        responses={201: RequestSubmitResponseSerializer, **PUBLIC_ERROR_RESPONSES,
                   400: OpenApiResponse(
                       {"type": "object", "additionalProperties": {},
                        "properties": {"feature": {"type": "string"}}},
                       description="Invalid submission or loans feature disabled.",
                   ),
                   423: OpenApiResponse(ErrorSerializer, description="Tenant frozen for migration.")},
        examples=[PUBLIC_REQUEST_SUBMIT_EXAMPLE],
    )
    def post(self, request, makerspace_slug, *args, **kwargs):
        makerspace = get_public_makerspace(makerspace_slug)
        require_feature(makerspace, "loans.enabled")
        _require_module(makerspace, "request_workflow")
        if module_enabled(makerspace, "membership"):
            require_current_term(makerspace, require_active_member_presence(request.user, makerspace).membership)
        else:
            # Waiver acceptance lives on MakerspaceMembership and cannot be recorded
            # with membership off. In this configuration the flow is public request ->
            # STAFF ACCEPT, and staff acceptance is the proposal-time control.
            require_active_account(request.user, makerspace)
        if _honeypot_filled(request.data):
            return _honeypot_response()

        serializer = RequestSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("website", None)

        product_ids = [item["product_id"] for item in data["items"]]
        products = _requestable_products(product_ids, makerspace)
        if len(products) != len(product_ids):
            raise ValidationError(
                {"items": "One or more products are unavailable for request."}
            )

        hardware_request = workflow.submit_request(
            makerspace,
            [
                {
                    "product": products[item["product_id"]],
                    "quantity": item["quantity"],
                }
                for item in data["items"]
            ],
            data["requested_for"],
            requester_principal=request.user,
            contact_snapshot=RequesterSnapshot(
                username=request.user.username,
                name=request.user.display_name,
                email=request.user.email,
                phone=request.user.phone,
            ),
            audit_actor=request.user,
        )
        return Response(
            RequestSubmitResponseSerializer(hardware_request).data,
            status=status.HTTP_201_CREATED,
        )


def _honeypot_response():
    decoy = SimpleNamespace(
        public_token=uuid.uuid4(),
        status=HardwareRequest.Status.PENDING_APPROVAL,
    )
    return Response(
        RequestSubmitResponseSerializer(decoy).data,
        status=status.HTTP_201_CREATED,
    )


def _honeypot_filled(payload):
    """True if the hidden anti-spam `website` field was populated. Real browsers never
    fill it; bots that auto-fill every field do. Read defensively from the raw payload."""
    try:
        value = payload.get("website", "")
    except AttributeError:
        return False
    return bool(str(value).strip())


def _requestable_products(product_ids, makerspace):
    return {
        product.pk: product
        for product in InventoryProduct.objects.filter(
            pk__in=product_ids,
            makerspace=makerspace,
            is_public=True,
            is_archived=False,
        )
    }


def _require_module(makerspace, module_key):
    from apps.makerspaces.editions import require_public_surface

    require_public_surface(module_key)
    if not module_enabled(makerspace, module_key):
        raise ValidationError({"module": f"{module_key} is disabled for this makerspace."})
