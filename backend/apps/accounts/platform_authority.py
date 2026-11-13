"""Who counts as an active platform superadmin for security and PII decisions."""

from apps.accounts.staff_identity import is_platform


def is_platform_superadmin(user):
    """A live platform account holding superuser status.

    The same predicate lifecycle decisions use: a staff or member account can never be a
    superadmin, and a retired, restricted or must-change-password account acts as nobody.
    """
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and not getattr(user, "is_tenant_dump_stub", False)
        and is_platform(user)
        and getattr(user, "is_superuser", False)
        and getattr(user, "is_active", False)
        and getattr(user, "retired_at", None) is None
        and getattr(user, "access_status", None) == "active"
        and not getattr(user, "must_change_password", False)
    )
