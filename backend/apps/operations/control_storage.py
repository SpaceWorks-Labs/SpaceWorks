"""Read-only control-plane storage summary using existing accounting, never S3 scans."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace


def storage_summary():
    tenants = Makerspace.objects.exclude(
        pk__in=rbac.superadmin_hidden_makerspace_ids(),
    ).order_by("-storage_bytes_used", "pk")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        database_bytes = cursor.fetchone()[0]
        cursor.execute(
            "SELECT schemaname, relname, pg_total_relation_size(relid) AS bytes "
            "FROM pg_stat_user_tables ORDER BY bytes DESC, schemaname, relname LIMIT 25"
        )
        tables = [{"schema": schema, "name": name, "bytes": size}
                  for schema, name, size in cursor.fetchall()]
    return {
        "database_bytes": database_bytes,
        "tables": tables,
        "tenants": list(tenants.values("id", "name", "storage_bytes_used")),
        "object_bytes": tenants.aggregate(total=Sum("storage_bytes_used"))["total"] or 0,
    }


@require_safe
def control_storage(request):
    user = request.user
    if not (user.is_active and user.is_superuser and user.access_status == "active"
            and not user.must_change_password):
        raise PermissionDenied
    response = TemplateResponse(request, "admin/storage.html", {
        **admin.site.each_context(request), **storage_summary(), "title": "Storage",
    })
    response["Cache-Control"] = "private, no-store"
    return response
