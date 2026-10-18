"""Account context never changes; retirement is an exact-tenant purge operation."""

from django.core.exceptions import ValidationError
from django.db import connections, router
from rest_framework.exceptions import PermissionDenied

RETIREMENT_GUC = "app.account_retirement_makerspace_id"


def require_member_account(user):
    if getattr(user, "account_kind", None) != "member" or user.retired_at is not None:
        raise PermissionDenied("This operation requires a member account.", code="member_account_required")


def guard_account_identity(user, *, using=None):
    if user.account_kind != "member" and any(getattr(user, field) for field in (
        "deletion_requested_at", "deletion_purge_after", "purge_started_at",
        "account_restored_at", "account_purged_at", "deletion_email_ciphertext", "deletion_username",
    )):
        raise ValidationError("Account deletion and restoration require a member account.")
    if user._state.adding:
        return
    using = using or router.db_for_write(type(user), instance=user)
    old = type(user)._base_manager.using(using).filter(pk=user.pk).values(
        "account_kind", "staff_makerspace_id", "retired_at",
    ).first()
    if old is None:
        return
    if old["account_kind"] != user.account_kind:
        raise ValidationError("Account kind is immutable.")
    if (old["staff_makerspace_id"] == user.staff_makerspace_id
            and old["retired_at"] == user.retired_at):
        return
    retirement = (
        old["account_kind"] == "staff" and old["staff_makerspace_id"] is not None
        and old["retired_at"] is None and user.staff_makerspace_id is None
        and user.retired_at is not None and not user.is_active
    )
    if retirement:
        with connections[using].cursor() as cursor:
            cursor.execute("SELECT current_setting(%s, true)", [RETIREMENT_GUC])
            retirement = cursor.fetchone()[0] == str(old["staff_makerspace_id"])
    if not retirement:
        raise ValidationError("Staff makerspace and retirement are immutable outside tenant purge.")
