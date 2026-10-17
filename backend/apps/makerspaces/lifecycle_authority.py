"""Platform authority for lifecycle decisions, independent of the admin caller."""

from django.core.exceptions import ValidationError


def require_platform_superadmin(actor):
    if not (
        getattr(actor, "is_authenticated", False)
        and getattr(actor, "account_kind", None) == "platform"
        and getattr(actor, "is_superuser", False)
        and getattr(actor, "is_active", False)
        and getattr(actor, "retired_at", None) is None
        and getattr(actor, "access_status", None) == "active"
        and not getattr(actor, "must_change_password", False)
    ):
        raise ValidationError("Only an active platform superadmin can manage makerspace lifecycle.")
