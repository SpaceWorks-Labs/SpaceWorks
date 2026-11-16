"""Platform authority for lifecycle decisions, independent of the admin caller."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError

from apps.accounts.staff_identity import is_platform


def require_platform_superadmin(actor):
    if not (
        getattr(actor, "is_authenticated", False)
        and is_platform(actor)
        and getattr(actor, "is_superuser", False)
        and getattr(actor, "is_active", False)
        and getattr(actor, "retired_at", None) is None
        and getattr(actor, "access_status", None) == "active"
        and not getattr(actor, "must_change_password", False)
    ):
        raise ValidationError(gettext("Only an active platform superadmin can manage makerspace lifecycle."))
