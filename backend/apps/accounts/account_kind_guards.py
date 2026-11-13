"""Object twins of the account-context triggers (one account per person).

The database is authoritative (``accounts_guard_context``); these guards give the same
answer earlier on ``save()``. Kind changes only in a unification run: staff->person
(the conversion migration) and person->merged shell (the merge engine).
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import connections, router
from rest_framework.exceptions import PermissionDenied

# Exact-tenant purge: the only path that deletes staff-track memberships. The legacy
# retirement name is still honoured for pre-unification shells and backup projections.
TENANT_PURGE_GUC = "app.tenant_purge_makerspace_id"
RETIREMENT_GUC = "app.account_retirement_makerspace_id"
UNIFICATION_GUC = "app.account_unification_run_id"
SHELL_IMPORT_GUC = "app.account_shell_import_job_id"
ACCOUNT_PURGE_GUC = "app.account_purge_user_id"


def require_member_account(user):
    """Refuse platform accounts and inert shells: the operation needs a person."""
    if (getattr(user, "account_kind", None) != "member" or user.retired_at is not None
            or getattr(user, "merged_into_id", None) is not None):
        raise PermissionDenied(gettext("This operation requires a personal account."), code="member_account_required")


def _setting(using, name):
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT current_setting(%s, true)", [name])
        return cursor.fetchone()[0] or ""


def guard_account_identity(user, *, using=None):
    if user.account_kind != "member" and any(getattr(user, field) for field in (
        "deletion_requested_at", "deletion_purge_after", "purge_started_at",
        "account_restored_at", "account_purged_at", "deletion_email_ciphertext", "deletion_username",
    )):
        raise ValidationError(gettext("Account deletion and restoration require a personal account."))
    if user._state.adding:
        return
    using = using or router.db_for_write(type(user), instance=user)
    old = type(user)._base_manager.using(using).filter(pk=user.pk).values(
        "account_kind", "staff_makerspace_id", "retired_at", "merged_into_id",
    ).first()
    if old is None:
        return
    if old["account_kind"] != user.account_kind:
        converting = old["account_kind"] == "staff" and user.account_kind == "member"
        merging = (old["account_kind"] == "member" and user.account_kind == "staff"
                   and user.merged_into_id is not None and not user.is_active)
        if not (converting or merging) or not _setting(using, UNIFICATION_GUC):
            raise ValidationError(gettext("Account kind changes only in an account-unification run."))
        return
    if old["merged_into_id"] != user.merged_into_id and not _setting(using, SHELL_IMPORT_GUC):
        raise ValidationError(gettext("A merged shell is remapped only by its tenant import."))
    if (old["staff_makerspace_id"] == user.staff_makerspace_id
            and old["retired_at"] == user.retired_at):
        return
    retirement = (
        old["account_kind"] == "staff" and old["staff_makerspace_id"] is not None
        and old["retired_at"] is None and user.staff_makerspace_id is None
        and user.retired_at is not None and not user.is_active
    )
    if not retirement or _setting(using, RETIREMENT_GUC) != str(old["staff_makerspace_id"]):
        raise ValidationError(gettext("Staff makerspace and retirement are immutable outside tenant purge."))
