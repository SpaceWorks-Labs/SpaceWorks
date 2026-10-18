"""Serialize new obligations against platform-wide account departure.

Call inside the writer's transaction, after its tenant/domain locks. Returning the
fresh User also prevents stale request/staff-selected instances bypassing departure.
NO KEY UPDATE permits unrelated foreign-key references to the account to continue.
"""

from rest_framework.exceptions import APIException

from apps.accounts.models import User


class AccountDeletionPending(APIException):
    status_code = 409
    default_code = "account_deletion_pending"
    default_detail = "This account has requested deletion and cannot take on new obligations."

    def __init__(self):
        super().__init__({"code": self.default_code, "detail": self.default_detail})


def lock_obligation_owner(user):
    """Lock the owner until commit and refuse an already archived account."""
    if user is None:
        return None
    locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
    if locked.deletion_requested_at is not None:
        raise AccountDeletionPending()
    # Return the caller's instance refreshed from the locked row: it may carry
    # request-scoped attribution (the claim audit context) that a freshly fetched
    # instance would silently drop, while callers still see committed field values.
    for field in User._meta.concrete_fields:
        setattr(user, field.attname, getattr(locked, field.attname))
    return user
