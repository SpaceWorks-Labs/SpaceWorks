"""Paying a pay link online (X19). Withdrawn by a rail tombstone, like every provider route.

The checkout is the charge's ordinary hosted page; the return URL is the public pay-link
completion page, because an account-less payer has no member area to come back to.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments.availability import online_payments_enabled_for
from apps.payments.checkout_expiry import live_checkout_url
from apps.payments.serializers import CheckoutUrlSerializer
from apps.payments.services import PaymentRailConflict, create_checkout_url
from apps.payments.throttles_l5 import PayLinkThrottle
from apps.payments.views_pay_links import live_link

UNAVAILABLE = {"detail": "Online payment is not available for this charge.", "code": "payments_unavailable"}


class PublicPayLinkCheckoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Payments"], summary="Open the hosted checkout for a pay link's charge", auth=[],
                   request=None,
                   responses={200: CheckoutUrlSerializer, 404: OpenApiResponse(ErrorSerializer),
                              409: OpenApiResponse(ErrorSerializer), 429: OpenApiResponse(ErrorSerializer),
                              503: OpenApiResponse(ErrorSerializer)})
    def post(self, request, token):
        link = live_link(token)
        payment = link.payment
        if payment.status != "pending" or not online_payments_enabled_for(payment):
            return Response(UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if live := live_checkout_url(payment):
            return Response({"checkout_url": live})
        from apps.tenant_migration.gate_runtime import tenant_write

        try:
            with tenant_write(payment.makerspace_id):
                checkout_url = create_checkout_url(payment.pk, actor=link.created_by)
        except PaymentRailConflict:
            return Response({"detail": "The charge already uses a different online rail.",
                             "code": "payment_rail_conflict"}, status=status.HTTP_409_CONFLICT)
        except Exception:  # noqa: BLE001 - provider failures answer a typed 503
            return Response(UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not checkout_url:
            return Response(UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"checkout_url": checkout_url})
