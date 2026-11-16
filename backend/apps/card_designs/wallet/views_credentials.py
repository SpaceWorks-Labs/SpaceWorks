"""Wallet-pass credentials: the Space Manager's per space, the superadmin's for the platform (223(l)).

* `GET/PATCH admin/makerspaces/<id>/wallet-credentials` -- manage_makerspace + `membership.wallet_passes` or `events.wallet_passes`.
* `GET/PATCH admin/platform/wallet-credentials` -- superadmin with recent re-authentication.

Secrets are write-only (never returned); each save, rotation and removal is audited with the
public certificate fingerprint only. A space with none of its own uses the platform's; with
neither, wallet buttons stay hidden.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveStaff, IsActiveSuperAdmin
from apps.admin_api.views_member_memberships import _makerspace
from apps.admin_api.views_membership_l4_common import staff_space
from apps.makerspaces.guards import SurfaceOff
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.openapi_errors import errors

from . import credential_service as service
from .serializers import (SpaceWalletCredentialsSerializer, WalletCredentialsInputSerializer,
                          WalletCredentialsSerializer)

TAG = "Wallet passes"
SPACE_ERRORS = errors(400, 401, 403, 404)


def _wallet_space(user, makerspace_id):
    """ID-11: either `membership.wallet_passes` or `events.wallet_passes` opens the credentials page."""
    try:
        return staff_space(user, makerspace_id, "wallet_passes", rbac.Action.MANAGE_MAKERSPACE)
    except SurfaceOff:
        space = _makerspace(user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE)
        if module_enabled(space, "events") and feature_enabled(space, "events.wallet_passes"):
            return space
        raise


@extend_schema_view(
    get=extend_schema(tags=[TAG], summary="This space's wallet-pass credentials (secrets are never returned)",
                      description="Needs manage_makerspace and `membership.wallet_passes` or `events.wallet_passes`. Shows only whether each "
                                  "platform is configured, its public identifiers, the certificate fingerprint and "
                                  "expiry, and which credentials actually sign this space's passes.",
                      responses={200: SpaceWalletCredentialsSerializer, **SPACE_ERRORS}),
    patch=extend_schema(tags=[TAG], summary="Save, rotate or remove this space's wallet-pass credentials",
                        description="Write-only secrets. Send `apple_*` and/or `google_*` fields to save or rotate; "
                                    "`clear_apple` / `clear_google` removes a group (the space then falls back to the "
                                    "platform's). The certificate, key and Team/Pass Type ID must agree. Audited.",
                        request=WalletCredentialsInputSerializer, responses={200: SpaceWalletCredentialsSerializer,
                                                                             **SPACE_ERRORS}),
)
class SpaceWalletCredentialsView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, makerspace_id):
        space = _wallet_space(request.user, makerspace_id)
        return Response(service.describe_space(space))

    def patch(self, request, makerspace_id):
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        space = _wallet_space(request.user, makerspace_id)
        assert_write_allowed(space.pk)
        data = WalletCredentialsInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = service.save(request.user, service.space_row(space, create=True), data.validated_data, scope="space",
                           makerspace=space)
        return Response({**service.describe_space(space), "reissue_needed": row.reissue_needed})


@extend_schema_view(
    get=extend_schema(tags=[TAG], summary="Platform wallet-pass credentials (secrets are never returned)",
                      responses={200: WalletCredentialsSerializer, **errors(401, 403)}),
    patch=extend_schema(tags=[TAG], summary="Save, rotate or remove the platform wallet-pass credentials",
                        description="Superadmin only, recent re-authentication. Used by every space that has none of "
                                    "its own while hosting other makerspaces is switched on (#234). Same write-only fields as the per-space route. Audited.",
                        request=WalletCredentialsInputSerializer,
                        responses={200: WalletCredentialsSerializer, **errors(400, 401, 403)}),
)
class PlatformWalletCredentialsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request):
        return Response(service.describe(service.platform_row()))

    def patch(self, request):
        data = WalletCredentialsInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = service.save(request.user, service.platform_row(create=True), data.validated_data, scope="platform")
        return Response({**service.describe(row), "reissue_needed": row.reissue_needed})
