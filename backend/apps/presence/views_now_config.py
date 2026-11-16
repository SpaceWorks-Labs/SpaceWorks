"""The public "now" page's own settings (decision 325a): which sections, in what order, how private."""
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.makerspaces.lookup import get_public_makerspace
from apps.tenant_migration.gate_runtime import tenant_write
from .display_config import clean_refresh
from .models_anthias import SpaceNowConfig
from .policy import PresenceError, require_staff
from .schema import ERRORS
from .serializers_anthias import NowConfigResponseSerializer, NowConfigSerializer
from .views_public import PresenceTVThrottle, PresenceTVUserThrottle, check_origin
from .views_staff import StaffPresenceView, staff_space

SECTIONS = ("here_now", "machines", "events", "public_stats", "opening_hours")
DEFAULT_SECTIONS = ["here_now", "machines", "events"]


def read(space):
    row = SpaceNowConfig.objects.filter(makerspace=space).first()
    if row is None:
        return {"sections": DEFAULT_SECTIONS, "privacy": "profiles", "refresh_seconds": 30}
    return {"sections": row.sections or DEFAULT_SECTIONS, "privacy": row.privacy, "refresh_seconds": row.refresh_seconds}


class StaffNowConfigView(StaffPresenceView):
    @extend_schema(tags=["Presence staff"], responses={200: NowConfigResponseSerializer, **ERRORS},
                   description="Requires manage_makerspace. Section keys: " + ", ".join(SECTIONS) + ".")
    def get(self, request, makerspace_id):
        return Response(read(staff_space(request, makerspace_id, settings=True)))

    @extend_schema(tags=["Presence staff"], request=NowConfigSerializer, responses={200: NowConfigResponseSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        space = staff_space(request, makerspace_id, settings=True)
        serializer = NowConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "sections" in data and (len(set(data["sections"])) != len(data["sections"])
                                   or any(s not in SECTIONS for s in data["sections"])):
            raise PresenceError("invalid_sections", gettext("Choose valid sections, each once."))
        if "refresh_seconds" in data:
            clean_refresh(data["refresh_seconds"])
        with tenant_write(space.pk):
            require_staff(request.user, space, settings=True)
            before = read(space)
            row, _ = SpaceNowConfig.objects.get_or_create(makerspace=space)
            for key, value in data.items():
                setattr(row, key, value)
            row.save()
            after = read(space)
            changed = sorted(k for k in data if before[k] != after[k])
            if changed:
                audit.record(request.user, "presence.now_config_updated", makerspace=space, target=row,
                             meta={"fields": changed})
        return Response(read(space))


class PublicNowConfigView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PresenceTVThrottle, PresenceTVUserThrottle]

    @extend_schema(tags=["Presence"], auth=[], responses={200: NowConfigResponseSerializer, **ERRORS},
                   description="Which sections the space's public page shows, in order, and how Here now is shown.")
    def get(self, request, makerspace_slug):
        space = get_public_makerspace(makerspace_slug)
        check_origin(request, space)
        return Response(read(space))
