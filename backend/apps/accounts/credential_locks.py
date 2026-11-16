"""One lock order for password changes, invitation redemption and recovery."""

from apps.accounts.models import StaffInvitation, User


def lock_token_issuance(user):
    """Fence a proved account snapshot before touching session/device rows.

    Issuers need no invitation/tenant locks and must not acquire them afterwards.
    Keep this lock through minting in the caller's atomic transaction.
    """
    from apps.accounts.session_issuance import lock_session_user

    return lock_session_user(user)


def lock_credentials(user_or_id, *, extra_user_ids=()):
    """Lock invitations and users; callers lock envelopes afterwards.

    Use inside an atomic transaction. The existence read keeps the DoesNotExist
    contract callers rely on for a concurrently deleted account.
    """
    user_id = getattr(user_or_id, "pk", user_or_id)
    # One account per person: no live account is bound to a staff tenant any more (an
    # inert shell holds no credentials), so there is no tenant row to lock first.
    User.objects.values("pk").get(pk=user_id)
    list(StaffInvitation.objects.select_for_update().filter(
        account_id=user_id,
    ).order_by("pk"))
    users = {row.pk: row for row in User.objects.select_for_update().filter(
        pk__in={user_id, *extra_user_ids},
    ).order_by("pk")}
    return users[user_id]
