"""Module install/uninstall surface for the Space Manager and the superadmin.

Owner decision #128 C-10 (superseding #77 Platform Q3): a Space Manager switches any
module on or off in their own space from the settings hub -- switching off keeps every
row, switching back on restores everything. On the managed platform, installing a module
whose usage is capped by a fair-use limit stays superadmin-only
(`module_switch_authority`), and every purge stays superadmin-only and outside this view.
The generic makerspace PATCH still refuses `enabled_modules`: this audited service path is
the only module writer.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.platform_authority import is_platform_superadmin
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_modules import (
    ModuleGroupListSerializer, ModuleInstallResultSerializer, ModuleUninstallResultSerializer,
)
from apps.makerspaces.module_switch_authority import limit_gated, may_install, may_uninstall
from apps.makerspaces.module_groups import deployment_app_status, grouped_module_status
from apps.makerspaces.module_install import (
    ModuleInstallError,
    install_module,
    uninstall_module,
)
from apps.makerspaces.module_profiles import PROFILES
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

class ModuleActionSerializer(serializers.Serializer):
    """The one field either mutation takes.

    A real class rather than `inline_serializer`, which returns an *instance* and so
    cannot be called with `data=` at request time.
    """

    key = serializers.CharField()


_ERRORS = {
    403: OpenApiResponse(description=(
        "Not this space's Space Manager or a superadmin; or, on the managed platform, a "
        "limit-gated module that only the superadmin may install."
    )),
    404: OpenApiResponse(
        description=(
            "Makerspace not found, archived, not active, or hidden from superadmins "
            "by its own manager."
        )
    ),
}


def _makerspace(actor, makerspace_id):
    # Archived spaces are excluded everywhere but /control/, and installing a module on
    # one would be a change nobody can see the effect of.
    # Resolved through rbac, like every other staff makerspace lookup.
    return get_object_or_404(
        rbac.scope_by_action(
            actor,
            rbac.Action.MANAGE_MAKERSPACE,
            servable_queryset(),
            field="id",
        ),
        pk=makerspace_id,
    )


def _groups(actor, makerspace):
    groups = grouped_module_status(makerspace)
    for group in groups:
        for row in group["modules"]:
            row["install_requires_superadmin"] = (
                not row["installed"] and not may_install(actor, makerspace, row["key"]))
            row["limits"] = limit_gated(makerspace, row["key"]) if not row["installed"] else []
    return groups


class ModuleGroupListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Platform"],
        summary="List module groups and their install state for a makerspace",
        responses={
            200: OpenApiResponse(ModuleGroupListSerializer, description="Grouped module status."),
            **errors(401, 403, 404),
        },
    )
    def get(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        return Response(
            {
                "groups": _groups(request.user, makerspace),
                # TOMBSTONED_APPS is a deployment decision: the superadmin's alone.
                "deployment": deployment_app_status() if is_platform_superadmin(request.user) else None,
                "profiles": [
                    {"key": key, "description": description}
                    for key, description in sorted(PROFILES.items())
                ],
            }
        )


class ModuleInstallView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Platform"],
        summary="Install a module and everything it requires",
        request=ModuleActionSerializer,
        responses={
            200: OpenApiResponse(ModuleInstallResultSerializer, description="Keys newly installed."),
            400: OpenApiResponse(description="Unknown module, or not shipped by this deployment."),
            **_ERRORS,
        },
    )
    def post(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        serializer = ModuleActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not may_install(request.user, makerspace, serializer.validated_data["key"]):
            raise PermissionDenied({"detail": gettext("This module has a usage limit on this platform; ask the "
                                    "platform administrator to install it."), "code": "module_install_superadmin_only"})
        try:
            added = install_module(makerspace, serializer.validated_data["key"], actor=request.user)
        except ModuleInstallError as exc:
            # 400 with the service's own message: it already explains *why* (unknown key,
            # tombstoned app, required by another module), and rewording it here would
            # give the operator less than the CLI does.
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"installed": added, "groups": _groups(request.user, makerspace)})


class ModuleUninstallView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Platform"],
        summary="Uninstall a module, keeping its data",
        description=(
            "Clears the capability key only. Rows, uploads and history are retained and "
            "reinstalling restores every surface. Destroying the data is a separate, "
            "irreversible step (`purge_module_data`) that is deliberately CLI-only."
        ),
        request=ModuleActionSerializer,
        responses={
            200: OpenApiResponse(ModuleUninstallResultSerializer, description="Keys uninstalled."),
            400: OpenApiResponse(description="Core module, or required by an installed module."),
            **_ERRORS,
        },
    )
    def post(self, request, makerspace_id):
        makerspace = _makerspace(request.user, makerspace_id)
        serializer = ModuleActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not may_uninstall(request.user, makerspace):
            raise PermissionDenied()
        try:
            removed = uninstall_module(makerspace, serializer.validated_data["key"], actor=request.user)
        except ModuleInstallError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"uninstalled": removed, "groups": _groups(request.user, makerspace)})
