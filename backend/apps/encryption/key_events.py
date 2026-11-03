"""What a space's managers may see of its key lifecycle: versions, jobs and their progress.

Read-only and makerspace-scoped. Rotation itself is ``/control/`` only (#120); there is no
Space-Manager key API. Nothing here carries key material, salts or browser key values.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts import rbac

from .models import MakerspaceEncryptionKey
from .models_rotation import KeyRotationJob, MakerspaceSearchKey, RetiredPublishableKey


def key_state(makerspace):
    active = MakerspaceEncryptionKey.objects.filter(makerspace=makerspace, status="active").first()
    search = MakerspaceSearchKey.objects.filter(makerspace=makerspace, status="active").first()
    retired = RetiredPublishableKey.objects.filter(makerspace=makerspace).order_by("-retired_at").first()
    return {
        "active_dek_version": active.version if active else None,
        "dek_versions": list(MakerspaceEncryptionKey.objects.filter(makerspace=makerspace)
                             .order_by("version").values("version", "status")),
        "search_key_version": search.version if search else None,
        "publishable_key_rotated_at": retired.retired_at if retired else None,
        "previous_publishable_key_valid_until": retired.valid_until if retired else None,
        "jobs": list(KeyRotationJob.objects.filter(makerspace=makerspace)[:20]),
    }


class KeyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = KeyRotationJob
        fields = ("id", "kind", "status", "from_version", "to_version", "rows_done", "rows_skipped",
                  "retained_versions", "error_code", "started_at", "updated_at", "completed_at")
        read_only_fields = fields


class MakerspaceKeyEventsView(ListAPIView):
    """GET makerspaces/<id>/security/key-events: rotations, re-keys and re-indexes of one space."""

    serializer_class = KeyEventSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["security"], summary="Key rotation and re-key history of one makerspace",
        description="Read-only. Visible to the space's managers (MANAGE_MAKERSPACE) and the superadmin. "
                    "Starting a rotation is a /control/ superadmin action; no key material is returned.",
        responses={200: KeyEventSerializer(many=True), 403: OpenApiResponse(description="Not a manager of this space."),
                   404: OpenApiResponse(description="Unknown or unservable makerspace.")},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        from apps.makerspaces.models import Makerspace
        makerspace_id = self.kwargs["makerspace_id"]
        scope = rbac.resolve_scope(self.request.user)
        if scope is not rbac.ALL and makerspace_id not in scope and not rbac.can(
                self.request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id):
            raise NotFound()
        if not Makerspace.objects.filter(pk=makerspace_id).exists():
            raise NotFound()
        if not rbac.can(self.request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id):
            raise PermissionDenied()
        return rbac.scope_by_action(self.request.user, rbac.Action.MANAGE_MAKERSPACE,
                                    KeyRotationJob.objects.filter(makerspace_id=makerspace_id))
