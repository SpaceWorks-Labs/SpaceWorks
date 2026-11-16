"""/control/ "Row-level security": mode, runtime-role contract, coverage and capabilities.

This is where report-only and inactive modes warn the operator (#128 C-25). Read-only.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe

from .capabilities import CAPABILITIES, ROUTE_CAPABILITIES, TASK_CAPABILITIES
from .checks import coverage_gaps
from .policies import build_plans
from .role_contract import status


@require_safe
def control_rls(request):
    user = request.user
    if not (user.is_active and user.is_superuser and user.access_status == "active"
            and not user.must_change_password):
        raise PermissionDenied
    plans, unresolvable = build_plans()
    state = status()
    response = TemplateResponse(request, "admin/tenant_rls/status.html", {
        **admin.site.each_context(request), "title": "Row-level security",
        "state": state, "scoped": len(plans), "gaps": coverage_gaps(), "unresolvable": unresolvable,
        "capabilities": sorted(CAPABILITIES.items()),
        "routes": sorted(ROUTE_CAPABILITIES.items()), "tasks": sorted(TASK_CAPABILITIES.items()),
    })
    response["Cache-Control"] = "private, no-store"
    return response
