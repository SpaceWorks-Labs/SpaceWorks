"""Apple's pass web service (PassKit), mounted at /api/v1/wallet/apple/v1/.

Apple's servers and devices call these with `Authorization: ApplePass <token>`; the
token is checked here against the stored digest (constant time), never logged. There
is no account and no session: `authentication_classes = []`. Each pass names its own
space, so no request crosses tenants.
"""
import hmac
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import http_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from ..models import WalletDeviceRegistration, WalletPass
from .credentials import apple_ready, digest

TAGS = ["Wallet passes"]


def _pass(request, pass_type, serial):
    if not apple_ready() or pass_type != settings.WALLET_APPLE_PASS_TYPE_ID:
        return None
    header = request.headers.get("Authorization", "")
    if not header.startswith("ApplePass "):
        return None
    row = WalletPass.objects.filter(serial=serial, platform="apple").select_related("makerspace").first()
    if row is None or not hmac.compare_digest(row.auth_token_digest, digest(header[len("ApplePass "):])):
        return None
    return row


class _Base(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


class ApplePassRegistrationView(_Base):
    @extend_schema(tags=TAGS, summary="Register a device for pass updates", request=OpenApiTypes.OBJECT,
                   responses={201: None, 200: None, **errors(401)})
    def post(self, request, device, pass_type, serial):
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        row = _pass(request, pass_type, serial)
        if row is None:
            return Response(status=401)
        assert_write_allowed(row.makerspace_id)
        push = str((request.data or {}).get("pushToken", ""))[:200]
        _registration, created = WalletDeviceRegistration.objects.update_or_create(
            wallet_pass=row, device_digest=digest(device), defaults={"push_token": push})
        return Response(status=201 if created else 200)

    @extend_schema(tags=TAGS, summary="Unregister a device", request=None, responses={200: None, **errors(401)})
    def delete(self, request, device, pass_type, serial):
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        row = _pass(request, pass_type, serial)
        if row is None:
            return Response(status=401)
        assert_write_allowed(row.makerspace_id)
        WalletDeviceRegistration.objects.filter(wallet_pass=row, device_digest=digest(device)).delete()
        return Response(status=200)


class ApplePassSerialsView(_Base):
    @extend_schema(tags=TAGS, summary="Serial numbers of this device's passes updated since a tag", request=None,
                   responses={200: OpenApiTypes.OBJECT, 204: None})
    def get(self, request, device, pass_type):
        if not apple_ready() or pass_type != settings.WALLET_APPLE_PASS_TYPE_ID:
            return Response(status=204)
        rows = WalletPass.objects.filter(devices__device_digest=digest(device), platform="apple")
        since = request.query_params.get("passesUpdatedSince", "")
        if since.isdigit():
            rows = rows.filter(last_updated_at__gt=datetime.fromtimestamp(int(since), tz=dt_timezone.utc))
        serials = list(rows.values_list("serial", flat=True))
        if not serials:
            return Response(status=204)
        return Response({"serialNumbers": serials, "lastUpdated": str(int(timezone.now().timestamp()))})


class ApplePassLatestView(_Base):
    @extend_schema(tags=TAGS, summary="The latest version of a pass", request=None,
                   responses={(200, "application/vnd.apple.pkpass"): OpenApiTypes.BINARY, **errors(401)})
    def get(self, request, pass_type, serial):
        from ..holders import registered
        from .apple import build_pkpass
        from .content import pass_content
        row = _pass(request, pass_type, serial)
        if row is None:
            return Response(status=401)
        kind = row.holder_kind
        if kind not in registered():
            return Response(status=401)
        response = HttpResponse(build_pkpass(row, pass_content(kind, getattr(row, kind))),
                                content_type="application/vnd.apple.pkpass")
        response["Last-Modified"] = http_date(row.last_updated_at.timestamp())
        return response


class ApplePassLogView(_Base):
    @extend_schema(tags=TAGS, summary="Device error log (accepted and dropped)", request=OpenApiTypes.OBJECT,
                   responses={200: None})
    def post(self, request):
        # Apple's diagnostics can echo URLs and tokens; nothing is stored or logged.
        return Response(status=200)
