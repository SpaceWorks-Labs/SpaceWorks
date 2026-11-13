"""Guest-pass wallet routes (decision 223(k) P3).

* `POST member/makerspaces/<id>/guest-passes/<pass_id>/wallet/<platform>` -- the holder asks for
  the link to add their OWN pass: Google gets the signed Save link, Apple a one-minute
  `.pkpass` download URL (so iOS opens it directly instead of through an authenticated fetch).
* `GET wallet/guest-pass/<token>.pkpass` -- that download; the signed token is the credential.
* `POST admin/makerspaces/<id>/guest-passes/scan` -- the desk confirms a pass QR (reads only).

All answer 404 while `membership.guest_passes` is off, and the wallet routes also while
`membership.wallet_passes` is off or no credentials resolve (a space's own, else the platform's).
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import GuestPass
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from . import guest
from .serializers import GuestPassScanInputSerializer, GuestPassScanResultSerializer, GuestPassWalletSerializer

TAG = "Wallet passes"


class GuestPassWalletView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=[TAG], summary="Add my guest pass to Apple or Google Wallet", request=None,
                   description="Holder only. Needs `membership.guest_passes`, `membership.wallet_passes` and "
                               "credentials for the platform. The pass is static: it shows the space, your display "
                               "name, the pass number and its validity, plus a QR that stops working when the pass is "
                               "revoked or ends. Audited.",
                   responses={201: GuestPassWalletSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id, pass_id, platform):
        require_member_account(request.user)
        if not request.user.is_active or request.user.access_status != "active":
            raise PermissionDenied()
        space = require_membership_feature(get_object_or_404(servable_queryset(), pk=makerspace_id), "guest_passes")
        row = get_object_or_404(GuestPass.objects.select_related("makerspace", "holder", "product"), pk=pass_id,
                                makerspace=space, holder=request.user)
        base = request.build_absolute_uri("/").rstrip("/")
        return Response(guest.issue_link(request.user, row, platform, base_url=base), status=201)


class GuestPassPkpassDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=[TAG], summary="Download a guest pass for Apple Wallet (signed one-minute link)", request=None,
                   responses={(200, "application/vnd.apple.pkpass"): OpenApiTypes.BINARY, **errors(404)})
    def get(self, request, token):
        row = guest.pass_for_download(token)
        response = HttpResponse(guest.build_pkpass(row), content_type="application/vnd.apple.pkpass")
        response["Cache-Control"] = "no-store"
        response["Content-Disposition"] = f'attachment; filename="guest-pass-{row.pk}.pkpass"'
        return response


class GuestPassScanView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "member_card_resolve"  # m17: people lookups share the card-resolve budget

    @extend_schema(tags=[TAG], summary="Check a guest pass QR at the desk",
                   description="manage_members in the space and `membership.guest_passes`. Reads only: a revoked, "
                               "expired or converted pass answers `valid: false` with the reason. Checking in is the "
                               "usual presence or desk check-in.",
                   request=GuestPassScanInputSerializer, responses={200: GuestPassScanResultSerializer,
                                                                   **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "guest_passes")
        body = GuestPassScanInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = guest.resolve_token(body.validated_data["token"], makerspace=space)
        return Response(GuestPassScanResultSerializer(guest.scan(row)).data)
