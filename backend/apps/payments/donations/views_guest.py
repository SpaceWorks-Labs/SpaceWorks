"""A guest giver's own pages, reached only by the signed link they were given.

The link names one gift (or pledge) and binds its random secret; an unknown, tampered or
moved link answers 404 like an unknown id, and the switch off answers 404 too. A guest sees
their gift, pays it, downloads their 80G receipt, and manages their pledge -- nothing else.
"""

from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.makerspaces.platform import feature_enabled
from apps.payments.serializers_l5 import ClaimSubmitSerializer, OwnClaimSerializer
from apps.payments.throttles_l5 import PayLinkThrottle
from apps.tenant_migration.gate_runtime import tenant_write

from . import serializers_public as s
from .gates import DONATIONS, PLEDGES, TAX, require_feature
from .identity import PLEDGE_SALT, STATUS_SALT, resolve_link
from .models import Donation, DonationPledge
from .views_public import ERRORS

INVALID = {"detail": "This link is not valid.", "code": "donation_link_invalid"}


def _gift(token):
    donation = resolve_link(Donation, "access_secret", token, STATUS_SALT, donor__isnull=True)
    if donation is None or not feature_enabled(donation.makerspace, DONATIONS):
        raise NotFound(INVALID)
    return donation


def _pledge(token):
    pledge = resolve_link(DonationPledge, "manage_secret", token, PLEDGE_SALT, donor__isnull=True)
    if pledge is None or not feature_enabled(pledge.makerspace, PLEDGES):
        raise NotFound(INVALID)
    return pledge


class GuestGiftView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Donations"], summary="A guest's own gift (signed link)", auth=[],
                   responses={200: s.GiftStatusSerializer, **ERRORS})
    def get(self, request, token):
        return Response(s.GiftStatusSerializer(s.gift_status(_gift(token), token=token)).data)


class GuestGiftCheckoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Donations"], summary="Open the hosted checkout for a guest's gift", auth=[], request=None,
                   description="503 `payments_unavailable` when online payment is off or the provider failed; the "
                               "gift stays payable offline.",
                   responses={200: s.GiftStatusSerializer, 503: OpenApiResponse(s.GiftStatusSerializer), **ERRORS})
    def post(self, request, token):
        from .services import checkout_url
        from .tax_receipts import payment_for

        donation = _gift(token)
        payment = payment_for(donation)
        with tenant_write(donation.makerspace_id):
            url = checkout_url(payment) if payment else ""
        body = s.GiftStatusSerializer(s.gift_status(donation, payment=payment, token=token, checkout=url)).data
        return Response(body, status=200 if url else 503)


class GuestGiftClaimView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Donations"], summary="Tell the space you paid a guest gift offline", auth=[],
                   description="Needs `billing.offline_claims`. One open claim per gift and one per reference; "
                               "staff confirm or reject it (the L5 claim queue).",
                   request=ClaimSubmitSerializer, responses={201: OwnClaimSerializer, 409: OpenApiResponse(), **ERRORS})
    def post(self, request, token):
        from apps.payments.offline_claims import submit_claim

        from .tax_receipts import payment_for

        donation = _gift(token)
        require_feature(donation.makerspace, "billing.offline_claims")
        payload = ClaimSubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with tenant_write(donation.makerspace_id):
            claim = submit_claim(payment_for(donation), claimant=None, **payload.validated_data)
        return Response(OwnClaimSerializer(claim).data, status=201)


class GuestTaxReceiptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Donations"], summary="Download a guest's 80G receipt (PDF)", auth=[],
                   responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, token):
        from .tax_receipt_pdf import pdf_response

        donation = _gift(token)
        require_feature(donation.makerspace, TAX)
        if not donation.tax_receipt:
            raise NotFound({"detail": gettext("No tax-exempt receipt was issued for this gift."), "code": "no_tax_receipt"})
        return pdf_response(donation)


class GuestPledgeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PayLinkThrottle]

    @extend_schema(tags=["Donations"], summary="A guest's own pledge (signed link)", auth=[],
                   responses={200: s.PledgeStatusSerializer, **ERRORS})
    def get(self, request, token):
        from .serializers_staff import pledge_status

        return Response(s.PledgeStatusSerializer(pledge_status(_pledge(token), token=token)).data)

    @extend_schema(tags=["Donations"], summary="Pause, resume, change or cancel a guest's pledge", auth=[],
                   description="Audited `pledge.paused|resumed|updated|cancelled`. A resumed pledge never "
                               "back-charges the paused periods.",
                   request=s.PledgeActionSerializer, responses={200: s.PledgeStatusSerializer, **ERRORS})
    def post(self, request, token):
        from .pledges import change_pledge
        from .serializers_staff import pledge_status
        from .services import clean_amount

        pledge = _pledge(token)
        payload = s.PledgeActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with tenant_write(pledge.makerspace_id):
            amount = clean_amount(pledge.makerspace, data["amount"]) if data["amount"] is not None else None
            pledge = change_pledge(pledge, actor=None, action=data["action"], amount=amount,
                                   interval=data["interval"])
        return Response(s.PledgeStatusSerializer(pledge_status(pledge, token=token)).data)
