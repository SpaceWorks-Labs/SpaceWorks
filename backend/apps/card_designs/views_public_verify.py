"""GET /api/v1/public/card-verifications/<token> -- the public card check (SPEC §7).

Uniform 404, throttle `card_verify` (30/min per client IP), and headers that keep the
answer out of caches, search engines and referrers.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.openapi import PUBLIC_API_AUTH_PARAMETERS
from apps.openapi_errors import errors

from .verification import check


class IssuerSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("space", "organisation", "event"))
    name = serializers.CharField()
    logo_url = serializers.CharField(allow_null=True)
    space_noun = serializers.ChoiceField(
        choices=("makerspace", "organization"), required=False,
        help_text="Space issuers only: the wording noun of the issuing space (decision 295).")


class HolderSerializer(serializers.Serializer):
    name = serializers.CharField(allow_null=True)
    photo_url = serializers.CharField(allow_null=True)


class CardVerificationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("valid", "expired", "revoked"))
    valid = serializers.BooleanField()
    issuer = IssuerSerializer()
    label = serializers.CharField(allow_null=True)
    number = serializers.CharField(allow_null=True)
    valid_until = serializers.CharField(allow_null=True)
    holder = HolderSerializer(allow_null=True)
    note = serializers.CharField(allow_blank=True)
    checked_at = serializers.DateTimeField()
    timezone = serializers.CharField(help_text="The issuing space's time zone, for the 'Checked at' footnote.")


HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
           "X-Robots-Tag": "noindex, nofollow, noarchive", "Referrer-Policy": "no-referrer"}


class CardVerificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_verify"

    @extend_schema(tags=["Public cards"], summary="Is this card valid?", parameters=PUBLIC_API_AUTH_PARAMETERS,
                   description="Valid, expired or revoked; the issuer, programme/plan/event, number and valid-until; "
                               "the holder's name and photo only with their opt-in. Revoked or expired is NOT valid. "
                               "Every hidden case answers the same 404. Never the desk QR, never any extra.",
                   responses={200: CardVerificationSerializer, **errors(404, 429)})
    def get(self, request, token):
        try:
            data = CardVerificationSerializer(check(token, request)).data
            response = Response(data)
        except NotFound as exc:
            response = self.handle_exception(exc)  # the standard error body, plus the same headers
        for name, value in HEADERS.items():
            response[name] = value
        return response
