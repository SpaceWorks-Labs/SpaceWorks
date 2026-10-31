"""Pay links (X19): staff create one for an account-less charge; the holder reads and pays it.

The public routes take the token in the path, show only what is owed and to whom (the
space, the charge label, the amount) and never who owes it. They answer 404 for an
unknown, expired, revoked or settled link, and while the space's `billing.pay_links`
switch is off. Paying online lives in `apps.payments_rail.views_pay_link_checkout`.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import feature_enabled
from apps.payments import pay_links
from apps.payments.l5_gates import action_space
from apps.payments.serializers_l5 import ClaimSubmitSerializer, OwnClaimSerializer, UpiDetailsSerializer
from apps.payments.throttles_l5 import PayLinkThrottle

ERRORS = {401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer)}


class PayLinkCreateSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=pay_links.MAX_DAYS, default=pay_links.DEFAULT_DAYS)
    email = serializers.EmailField(required=False, allow_blank=True, default="",
                                   help_text="Optional: email the link once to the payer. Never stored.")


class PayLinkSerializer(serializers.Serializer):
    url = serializers.CharField()
    expires_at = serializers.DateTimeField()
    emailed = serializers.BooleanField()


class PublicPayLinkSerializer(serializers.Serializer):
    makerspace = serializers.CharField()
    label = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    online_available = serializers.BooleanField()
    upi = UpiDetailsSerializer(allow_null=True)
    instructions = serializers.CharField(allow_blank=True)
    claimable = serializers.BooleanField()


class StaffPayLinkView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Create a pay link for an account-less charge staff raised",
                   description="Requires record_payment and `billing.pay_links`. One live link per charge: a new "
                               "link revokes the previous one. 409 `payment_terminal`, `pay_link_has_account` or "
                               "`pay_link_not_staff_raised`. Audited `payment.pay_link_created`.",
                   request=PayLinkCreateSerializer,
                   responses={201: PayLinkSerializer, 409: OpenApiResponse(ErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id, payment_id):
        from apps.accounts import rbac

        action_space(request, makerspace_id, rbac.Action.RECORD_PAYMENT, "billing.pay_links")
        payload = PayLinkCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        link, token = pay_links.create_link(actor=request.user, makerspace_id=makerspace_id, payment_id=payment_id,
                                            **payload.validated_data)
        return Response({"url": pay_links.link_url(token), "expires_at": link.expires_at,
                         "emailed": bool(payload.validated_data["email"])}, status=201)


def live_link(token):
    link = pay_links.resolve(token)
    if link is None or not feature_enabled(link.payment.makerspace, "billing.pay_links"):
        raise NotFound({"detail": "This payment link is not valid.", "code": "pay_link_invalid"})
    return link


class PublicPayLinkView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Payments"], summary="Read what a pay link asks for", auth=[],
                   description="Public. Shows the space, the charge label and the amount only. 404 "
                               "`pay_link_invalid` for an unknown, expired, revoked or settled link.",
                   responses={200: PublicPayLinkSerializer, 404: OpenApiResponse(ErrorSerializer),
                              429: OpenApiResponse(ErrorSerializer)})
    def get(self, request, token):
        from apps.payments.availability import online_payments_enabled_for
        from apps.payments.payment_rows_l5 import offline_collection

        from apps.tenant_migration.gate_runtime import tenant_write

        link = live_link(token)
        payment = link.payment
        with tenant_write(payment.makerspace_id):
            pay_links.mark_used(link)
        offline = offline_collection(payment)
        return Response({
            "makerspace": payment.makerspace.name,
            "label": payment.subject_label or payment.get_subject_type_display(),
            "amount": f"{payment.amount:.2f}", "currency": payment.currency, "status": payment.status,
            "expires_at": link.expires_at,
            "online_available": payment.status == "pending" and online_payments_enabled_for(payment),
            "upi": offline["upi"], "instructions": offline["instructions"], "claimable": offline["claimable"]})


class PublicPayLinkClaimView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Payments"], summary="Tell the space you paid this link's charge offline", auth=[],
                   description="Public, rate-limited, needs `billing.offline_claims`. One open claim per charge "
                               "and one claim per reference. Staff confirm or reject it.",
                   request=ClaimSubmitSerializer,
                   responses={201: OwnClaimSerializer, 404: OpenApiResponse(ErrorSerializer),
                              409: OpenApiResponse(ErrorSerializer), 429: OpenApiResponse(ErrorSerializer)})
    def post(self, request, token):
        from apps.payments.offline_claims import submit_claim
        from apps.tenant_migration.gate_runtime import tenant_write

        link = live_link(token)
        if not feature_enabled(link.payment.makerspace, "billing.offline_claims"):
            raise NotFound({"detail": "Offline claims are turned off here.", "code": "feature_disabled"})
        payload = ClaimSubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(link.payment.makerspace_id):
            claim = submit_claim(link.payment, claimant=None, pay_link=link, **payload.validated_data)
        return Response(OwnClaimSerializer(claim).data, status=201)
