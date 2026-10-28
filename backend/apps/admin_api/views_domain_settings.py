"""GET/PATCH one domain's feature switches and settings, for that domain's manager.

One endpoint keyed by domain rather than one per domain or a per-key authorizer: the
domain in the PATH decides the single action checked (manage_events, manage_bookings,
manage_machines, edit_inventory), so authorization is one `scope_by_action` exactly like
the makerspace PATCH, and a body naming another domain's key is a plain 400 rather than a
partially-applied write.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_domain_settings import (
    DomainSettingsSerializer,
    DomainSettingsUpdateSerializer,
)
from apps.makerspaces.domain_settings import (
    DOMAINS,
    apply_domain_settings,
    can_edit,
    describe,
    key_permissions,
)
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors


_DOMAIN = OpenApiParameter(
    "domain", OpenApiTypes.STR, OpenApiParameter.PATH, enum=sorted(DOMAINS),
    description=(
        "events -> manage_events, bookings -> manage_bookings, machines -> "
        "manage_machines, inventory -> edit_inventory."
    ),
)
_NOT_FOUND = errors(404, e404=(
    "Unknown domain, or the makerspace is not servable or the actor lacks this "
    "domain's action there."
))


class MakerspaceDomainSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    def _makerspace(self, request, makerspace_id, domain):
        spec = DOMAINS.get(domain)
        if spec is None:
            raise Http404
        spaces = rbac.scope_by_action(
            request.user, spec.action, servable_queryset(), field="id",
        )
        makerspace = get_object_or_404(spaces, pk=makerspace_id)
        self.check_object_permissions(request, makerspace)
        return makerspace

    @extend_schema(
        tags=["Admin makerspaces"],
        summary="Read one domain's feature switches and settings",
        parameters=[_DOMAIN],
        responses={200: DomainSettingsSerializer, **errors(401, 403), **_NOT_FOUND},
    )
    def get(self, request, makerspace_id, domain):
        makerspace = self._makerspace(request, makerspace_id, domain)
        return Response(DomainSettingsSerializer(self._describe(request, makerspace, domain)).data)

    def _describe(self, request, makerspace, domain):
        return describe(makerspace, domain, can_edit(request.user, makerspace, domain),
                        key_permissions(request.user, makerspace, domain))

    @extend_schema(
        tags=["Admin makerspaces"],
        summary="Update one domain's feature switches and settings",
        description=(
            "Toggles only this domain's feature keys (others keep their stored value) and "
            "writes its settings through the same validation as the makerspace PATCH: "
            "capability prerequisites and installed modules are enforced. Keys of another "
            "domain, `payments.*`/`charges.*`, `enabled_modules` and any unknown field are "
            "refused with 400. Every key the body changes is authorized by the settings-"
            "authority layer (#101): the Space Manager always, a module manager only with "
            "this module's grant and never past a lock; the Inventory Manager changes rental "
            "timing without a grant (C-11d). Audited as settings.changed per key, plus "
            "makerspace.updated / makerspace.features_changed."
        ),
        parameters=[_DOMAIN],
        request=DomainSettingsUpdateSerializer,
        responses={
            200: DomainSettingsSerializer,
            400: OpenApiResponse(description=(
                "A foreign or unknown key, a missing prerequisite feature or module, or "
                "an invalid setting value."
            )),
            403: OpenApiResponse(description=(
                "Not active staff; `setting_not_delegated` (no grant for this module, a "
                "finance/security key, or a type-scoped Machine Manager while machines "
                "outside their types exist); or `setting_locked` (a Space Manager lock)."
            )),
            **errors(401),
            **_NOT_FOUND,
        },
    )
    def patch(self, request, makerspace_id, domain):
        makerspace = self._makerspace(request, makerspace_id, domain)
        serializer = DomainSettingsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        makerspace = apply_domain_settings(
            request.user, makerspace, domain,
            serializer.validated_data.get("features", {}),
            serializer.validated_data.get("settings", {}),
        )
        return Response(DomainSettingsSerializer(self._describe(request, makerspace, domain)).data)
