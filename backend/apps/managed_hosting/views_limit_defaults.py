"""Platform default limits (superadmin) and the Space Manager's read-only limits and usage (decision 328a)."""
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveStaff, IsActiveSuperAdmin
from apps.makerspaces.limit_modules import group_of, groups_payload, module_of
from apps.openapi_errors import errors

from .limit_catalogue import label_of, registry_keys, unit_of
from .limit_defaults import all_defaults
from .limit_overview import overview_rows
from .limit_services import set_platform_defaults
from .views_space import _space

TAGS = ["Managed hosting"]


class LimitGroupSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="A module group key (the headings of the module switch screens).")
    label = serializers.CharField(help_text="Translated group name.")


class LimitDefaultRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=["count", "bytes"])
    module = serializers.CharField(help_text="The module that owns this limit (`limit_modules.KEY_MODULE`).")
    group = serializers.CharField(help_text="The module group it is shown under.")
    default = serializers.IntegerField(allow_null=True, help_text="null = no platform default (unlimited, the default).")


class LimitDefaultsSerializer(serializers.Serializer):
    groups = LimitGroupSerializer(many=True)
    rows = LimitDefaultRowSerializer(many=True)


class LimitDefaultsUpdateSerializer(serializers.Serializer):
    defaults = serializers.DictField(
        help_text="Keys to change: a non-negative integer sets the platform default (bytes for byte keys); "
                  "null or -1 removes it. Keys left out are unchanged. Unknown or boolean keys are refused.")


def _payload():
    stored = all_defaults()
    rows = [{"key": key, "label": label_of(key), "unit": unit_of(key), "module": module_of(key),
             "group": group_of(key), "default": stored.get(key)} for key in registry_keys()]
    return {"groups": groups_payload(), "rows": rows}


# The column is a PostgreSQL bigint: anything larger is a 400 here, never a 500 at the database.
MAX_DEFAULT = 2**63 - 1


def _clean(raw):
    allowed = set(registry_keys())
    out = {}
    for key, value in raw.items():
        if key not in allowed:
            raise serializers.ValidationError({key: gettext("Unknown limit key.")})
        if value is None or value == -1:
            out[key] = None
        elif isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_DEFAULT:
            raise serializers.ValidationError({key: gettext("Use a whole number from 0 to %(max)s, -1 or null.")
                                               % {"max": MAX_DEFAULT}})
        else:
            out[key] = value
    return out


class PlatformLimitDefaultsView(RecentReauthenticationMixin, APIView):
    """Resolution order everywhere: a space's own override, a hosted space's plan, this default, then no limit."""

    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read the platform default for every limit key",
                   responses={200: LimitDefaultsSerializer, **errors(401, 403)})
    def get(self, request):
        return Response(_payload())

    @extend_schema(tags=TAGS, summary="Set or clear platform default limits", request=LimitDefaultsUpdateSerializer,
                   responses={200: LimitDefaultsSerializer, **errors(400, 401, 403)})
    def put(self, request):
        body = LimitDefaultsUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        set_platform_defaults(request.user, _clean(body.validated_data["defaults"]))
        return Response(_payload())


class LimitUsageRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=["count", "bytes"])
    module = serializers.CharField()
    group = serializers.CharField()
    limit = serializers.IntegerField(allow_null=True, help_text="null = unlimited.")
    used = serializers.IntegerField(allow_null=True)
    percent = serializers.FloatField(allow_null=True)
    level = serializers.ChoiceField(choices=["ok", "warning", "limit"], help_text="`warning` from 80 %, `limit` at 100 %.")
    source = serializers.ChoiceField(choices=["override", "plan", "default", "unlimited"])


class SpaceLimitsUsageSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    groups = LimitGroupSerializer(many=True)
    rows = LimitUsageRowSerializer(many=True)


class SpaceLimitsUsageView(APIView):
    """Read-only for the Space Manager (and a superadmin): every limited key of THIS space with its usage."""

    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Read this space's limits and usage, grouped by module",
                   responses={200: SpaceLimitsUsageSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id, plans_required=False)
        return Response({"makerspace_id": space.pk, "groups": groups_payload(),
                         "rows": overview_rows(space, limited_only=True)})
