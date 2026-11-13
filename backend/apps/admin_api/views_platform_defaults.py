"""Open item C13: the platform's module defaults and its list of platform admins (superadmin only).

Module defaults are READ-ONLY here: what a new space starts with is decided per space by the
setup-areas question (decision 254) on top of the registry's core/default flags, so a second,
platform-wide default switch would contradict it. The screen shows each module's default and how
many spaces have it on. The admin list carries no contact detail (no email, phone or display
name), the same masking as the platform account lookup, and reading it is audited.
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.module_registry_catalog import MODULES
from apps.makerspaces.servability import servable_queryset
from apps.operations.platform_scope import _platform_context_for_view

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (401, 403, 429)}
NO_STORE = {"Cache-Control": "private, no-store"}


class PlatformDefaultsThrottle(UserRateThrottle):
    scope = "platform_queues"
    rate = "30/min"


class ModuleDefaultSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    group = serializers.CharField()
    always_on = serializers.BooleanField(help_text="Core: every space has it and it cannot be switched off.")
    on_for_new_spaces = serializers.BooleanField()
    spaces_on = serializers.IntegerField(help_text="Active spaces with this module switched on.")


class ModuleDefaultsSerializer(serializers.Serializer):
    spaces_total = serializers.IntegerField()
    modules = ModuleDefaultSerializer(many=True)


class PlatformAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    is_active = serializers.BooleanField()
    mfa_enabled = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)


class PlatformAdminsSerializer(serializers.Serializer):
    admins = PlatformAdminSerializer(many=True)


class _PlatformView(APIView):
    permission_classes = [IsActiveSuperAdmin]
    throttle_classes = [PlatformDefaultsThrottle]
    http_method_names = ["get", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _platform_context_for_view(request)  # superadmin browser session only


def module_defaults():
    spaces = list(servable_queryset().filter(archived_at__isnull=True).values_list("enabled_modules", flat=True))
    rows = []
    for module in MODULES:
        if not module.frontend_exposed:
            continue
        rows.append({
            "key": module.key, "label": module.label, "description": module.description, "group": module.group,
            "always_on": module.is_core, "on_for_new_spaces": module.is_core or module.default_enabled,
            "spaces_on": sum(1 for enabled in spaces if module.is_core or module.key in (enabled or [])),
        })
    return {"spaces_total": len(spaces), "modules": rows}


def platform_admins():
    rows = (User.objects.filter(Q(is_superuser=True) | Q(role=User.Role.SUPERADMIN), is_tenant_dump_stub=False)
            .select_related("usermfa").order_by("username"))
    return [{"id": user.pk, "username": user.username, "is_active": user.is_active,
             "mfa_enabled": bool(getattr(user, "usermfa", None) and user.usermfa.enabled_at and user.usermfa.secret),
             "last_login": user.last_login} for user in rows]


class PlatformModuleDefaultsView(_PlatformView):
    @extend_schema(tags=["Platform"], summary="Module defaults for new spaces and how many spaces use each",
                   description="Superadmin only, read-only. A new space starts with the always-on modules plus "
                               "the areas chosen at setup.",
                   responses={200: ModuleDefaultsSerializer, **ERRORS})
    def get(self, request):
        return Response(module_defaults(), headers=NO_STORE)


class PlatformAdminListView(_PlatformView):
    @extend_schema(tags=["Platform"], summary="Platform admins (superadmin accounts), audited",
                   description="User name, active, two-step sign-in and last sign-in only; no contact details.",
                   responses={200: PlatformAdminsSerializer, **ERRORS})
    def get(self, request):
        rows = platform_admins()
        audit.record(request.user, "platform.admins_viewed", target_type="platform_admins", meta={"admins": len(rows)})
        return Response({"admins": rows}, headers=NO_STORE)
