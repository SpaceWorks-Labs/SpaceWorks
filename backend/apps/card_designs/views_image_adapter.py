"""Image-adapter provider settings: the Space Manager's per space, the superadmin's for the platform (D314c).

* `GET/PATCH admin/makerspaces/<id>/image-adapter` and `POST .../image-adapter/test` -- manage_makerspace and the
  `cards.photo_cutout` switch (typed 404 when off).
* `GET/PATCH admin/platform/image-adapter` and `POST .../test` -- superadmin, recent re-authentication on writes.

The shared secret is write-only (never returned). A space with none of its own uses the platform's unless it
opted out. The contract a provider implements is in `docs/image-adapters/`.
"""
from django.utils.translation import gettext
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveStaff, IsActiveSuperAdmin
from apps.admin_api.views_member_memberships import _makerspace
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from apps.outbound_throttles import IMAGE_ADAPTER_TEST_THROTTLES

from .image_adapter import provider
from .serializers_image_adapter import (ImageAdapterInputSerializer, ImageAdapterSerializer,
                                        ImageAdapterTestSerializer, SpaceImageAdapterSerializer)
from .switches import PHOTO_CUTOUT

TAG = "Card photo eraser"


def _space(user, makerspace_id):
    space = _makerspace(user, makerspace_id, rbac.Action.MANAGE_MAKERSPACE)
    if not feature_enabled(space, PHOTO_CUTOUT):
        raise Http404()
    return space


@extend_schema_view(
    get=extend_schema(tags=[TAG], summary="This space's eraser provider (the secret is never returned)",
                      description="Needs manage_makerspace and `cards.photo_cutout`. Shows the address, a public "
                                  "fingerprint of the secret, the last test and which provider actually serves the space.",
                      responses={200: SpaceImageAdapterSerializer, **errors(401, 403, 404)}),
    patch=extend_schema(tags=[TAG], summary="Save, rotate or remove this space's eraser provider",
                        description="Write-only secret. A space provider must be a public https address. "
                                    "`clear` removes it (the space then uses the platform's); "
                                    "`use_platform_provider` opts out of the platform fallback. Audited.",
                        request=ImageAdapterInputSerializer,
                        responses={200: SpaceImageAdapterSerializer, **errors(400, 401, 403, 404)}),
)
class SpaceImageAdapterView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, makerspace_id):
        return Response(provider.describe_space(_space(request.user, makerspace_id)))

    def patch(self, request, makerspace_id):
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        space = _space(request.user, makerspace_id)
        assert_write_allowed(space.pk)
        data = ImageAdapterInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        provider.save(request.user, provider.space_row(space, create=True), data.validated_data, scope="space",
                      makerspace=space)
        return Response(provider.describe_space(space))


@extend_schema(tags=[TAG], summary="Test this space's own provider (signed health check)", request=None,
               responses={200: ImageAdapterTestSerializer, **errors(400, 401, 403, 404, 429)})
class SpaceImageAdapterTestView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = IMAGE_ADAPTER_TEST_THROTTLES  # a test waits on an outside host (L-C2)

    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        row = provider.space_row(space)
        if row is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": gettext("Save the provider's address and secret first.")})
        return Response(provider.test(request.user, row, scope="space", makerspace=space))


@extend_schema_view(
    get=extend_schema(tags=[TAG], summary="Platform eraser provider (the secret is never returned)",
                      responses={200: ImageAdapterSerializer, **errors(401, 403)}),
    patch=extend_schema(tags=[TAG], summary="Save, rotate or remove the platform eraser provider",
                        description="Superadmin only, recent re-authentication. Spaces with no provider of their own "
                                    "use it while `cards.photo_cutout` is on for them. Platform providers may be a "
                                    "private-network address (a compose service). Audited.",
                        request=ImageAdapterInputSerializer,
                        responses={200: ImageAdapterSerializer, **errors(400, 401, 403)}),
)
class PlatformImageAdapterView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request):
        return Response(provider.describe_platform())

    def patch(self, request):
        data = ImageAdapterInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = provider.save(request.user, provider.platform_row(create=True), data.validated_data, scope="platform")
        return Response(provider._public(row))


@extend_schema(tags=[TAG], summary="Test the platform provider (signed health check)", request=None,
               responses={200: ImageAdapterTestSerializer, **errors(400, 401, 403, 429)})
class PlatformImageAdapterTestView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    throttle_classes = IMAGE_ADAPTER_TEST_THROTTLES  # a test waits on an outside host (L-C2)

    def post(self, request):
        row = provider.platform_row()
        if row is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": gettext("Save the provider's address and secret first.")})
        return Response(provider.test(request.user, row, scope="platform"))
