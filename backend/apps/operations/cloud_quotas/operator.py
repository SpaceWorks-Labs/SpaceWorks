"""Reload current platform authority before supervised accounting mutations."""
def require_operator(actor):
    from apps.accounts.models import User
    from apps.admin_api.permissions import active_user
    from apps.tenant_migration.services_import_job import _require_superadmin
    current = User.objects.filter(pk=getattr(actor, "pk", None)).first()
    _require_superadmin(current)
    if not active_user(current) or current.retired_at is not None:
        raise ValueError("platform_operator_required")
    return current
