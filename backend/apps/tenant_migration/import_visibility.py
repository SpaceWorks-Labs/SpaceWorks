"""Visibility rules for tenant import targets."""

from apps.accounts.models import User


def scope_import_target_makerspaces(actor, queryset):
    """Every target for a superadmin, without applying normal servability.

    Import targets legitimately remain non-servable until cutover, so this must not
    filter them the way tenant RBAC does.
    """
    is_superadmin = bool(
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and (actor.is_superuser or actor.role == User.Role.SUPERADMIN)
    )
    return queryset if is_superadmin else queryset.none()
