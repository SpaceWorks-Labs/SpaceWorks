"""The Space Manager's plan usage and hosting invoices (#187A), plus the platform's own
provider callbacks for online payment. All 404 while MANAGED_PLANS_ENABLED is off."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from . import online, serializers as s
from .availability import require_online_billing, require_plans_enabled
from .models import HostingInvoice
from .usage import plan_usage

TAGS = ["Managed hosting"]


def _space(request, makerspace_id, *, plans_required=True):
    if plans_required:
        require_plans_enabled()
    space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
    if not rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, space.pk):
        raise PermissionDenied(gettext("Managing this makerspace is required."))
    return space


class SpacePlanUsageView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read this space's hosting plan and usage against it",
                   responses={200: s.HostingPlanUsageSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        return Response(s.HostingPlanUsageSerializer(plan_usage(_space(request, makerspace_id, plans_required=False))).data)


class SpaceInvoiceListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List this space's hosting invoices",
                   responses={200: s.SpaceHostingInvoiceSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        rows = HostingInvoice.objects.filter(makerspace=space).prefetch_related("receipts").exclude(status="void")
        return Response(s.SpaceHostingInvoiceSerializer(rows, many=True).data)


class SpaceInvoiceCheckoutView(APIView):
    """The payer acts: the Space Manager opens the checkout; nothing is charged otherwise."""

    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Open an online checkout for a hosting invoice", request=None,
                   responses={200: s.HostingCheckoutSerializer, **errors(401, 403, 404, 409)})
    def post(self, request, makerspace_id, invoice_id):
        space = _space(request, makerspace_id)
        require_online_billing()
        get_object_or_404(HostingInvoice, pk=invoice_id, makerspace=space)
        return Response(s.HostingCheckoutSerializer({"url": online.start_checkout(space.pk, invoice_id, actor=request.user)}).data)


class _ProviderCallbackView(APIView):
    verify = None
    signature_header = ""

    def receive(self, request):
        require_online_billing()
        try:
            event = type(self).verify(request.body, request.headers.get(self.signature_header, ""))
        except Exception:
            return Response({"detail": gettext("Invalid signature.")}, status=400)
        if event and str(event.get("invoice_id") or "").isdigit():
            from apps.space_controls.write_policy import permitted, BOTH
            from apps.tenant_migration.gate_runtime import tenant_write
            space_id = HostingInvoice.objects.filter(pk=int(event["invoice_id"])).values_list(
                "makerspace_id", flat=True).first()
            # Settlement participates in the tenant gate but is permitted in every state:
            # money a payer already sent must settle even in a paused or read-only space.
            with permitted(BOTH):
                if space_id:
                    with tenant_write(space_id):
                        online.settle(event)
                else:
                    online.settle(event)
        return Response({"received": True})


_RECEIVED = inline_serializer("HostingCallbackReceived", {"received": serializers.BooleanField()})


class StripeHostingCallbackView(_ProviderCallbackView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    verify = staticmethod(online.verify_stripe)
    signature_header = "Stripe-Signature"

    @extend_schema(tags=TAGS, summary="Stripe callback for hosting invoices (signed)", request=None,
                   responses={200: OpenApiResponse(_RECEIVED, description="Received."), **errors(400, 404)})
    def post(self, request):
        return self.receive(request)


class RazorpayHostingCallbackView(_ProviderCallbackView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    verify = staticmethod(online.verify_razorpay)
    signature_header = "X-Razorpay-Signature"

    @extend_schema(tags=TAGS, summary="Razorpay callback for hosting invoices (signed)", request=None,
                   responses={200: OpenApiResponse(_RECEIVED, description="Received."), **errors(400, 404)})
    def post(self, request):
        return self.receive(request)
