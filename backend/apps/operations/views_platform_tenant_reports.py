"""Explicit platform read surface over the canonical tenant report handlers.

No tenant session is minted: each handler retains its report/action/module checks.
The platform surface also hard-blocks hidden tenants before any data is read.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from .platform_scope import _platform_context_for_view
from .views_dashboard_api import DashboardView
from .views_reports import AnalyticsView, ReportCatalogView, ReportExportView


class PlatformTenantReadMixin:
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _platform_context_for_view(request)  # Also refuses native authority.
        get_object_or_404(
            servable_queryset(Makerspace.objects.filter(superadmin_access_enabled=True)),
            pk=kwargs["makerspace_id"],
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response


@extend_schema(tags=["Platform tenant reports"], description="Platform browser read only. Hidden tenants are blocked; the canonical tenant report RBAC and module checks apply.")
class PlatformTenantCatalogView(PlatformTenantReadMixin, ReportCatalogView):
    pass


@extend_schema(tags=["Platform tenant reports"], description="Platform browser read only. Hidden tenants are blocked; the canonical tenant report RBAC and module checks apply.")
class PlatformTenantAnalyticsView(PlatformTenantReadMixin, AnalyticsView):
    pass


@extend_schema(tags=["Platform tenant reports"], description="Platform browser read only. Hidden tenants are blocked; the canonical dashboard action checks apply.")
class PlatformTenantDashboardView(PlatformTenantReadMixin, DashboardView):
    pass


@extend_schema(tags=["Platform tenant reports"], description="Platform browser export only. Hidden tenants are blocked; the canonical export RBAC, module checks and render throttle apply.")
class PlatformTenantExportView(PlatformTenantReadMixin, ReportExportView):
    pass
