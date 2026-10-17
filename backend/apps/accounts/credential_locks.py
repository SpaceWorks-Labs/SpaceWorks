"""One lock order for password changes, invitation redemption and recovery."""

from apps.accounts.models import StaffInvitation, User
from apps.makerspaces.models import Makerspace


def lock_token_issuance(user):
    """Fence a proved account snapshot before touching session/device rows.

    Issuers need no invitation/tenant locks and must not acquire them afterwards.
    Keep this lock through minting in the caller's atomic transaction.
    """
    from rest_framework.exceptions import AuthenticationFailed

    try:
        locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
    except User.DoesNotExist as exc:
        raise AuthenticationFailed("Account is not available.") from exc
    if locked.credential_generation != user.credential_generation:
        raise AuthenticationFailed("Account credentials have changed.")
    for attr in ("_mfa_verified_version", "_mfa_provider_verified", "_mfa_source"):
        if hasattr(user, attr):
            setattr(locked, attr, getattr(user, attr))
    return locked


def lock_credentials(user_or_id, *, extra_user_ids=()):
    """Lock tenant, invitations and users; callers lock envelopes afterwards.

    Use inside an atomic transaction. Reading immutable kind/tenant identifiers
    before locking avoids joining the nullable staff tenant FK in a locking query.
    Taking the tenant first serializes creation of invitations as well as existing
    rows, so an empty invitation queryset does not leave an issuance race.
    """
    user_id = getattr(user_or_id, "pk", user_or_id)
    identity = User.objects.values("account_kind", "staff_makerspace_id").get(pk=user_id)
    if identity["account_kind"] == User.AccountKind.STAFF:
        space_id = identity["staff_makerspace_id"]
        if space_id is not None:
            Makerspace.objects.select_for_update(no_key=True).get(pk=space_id)
    list(StaffInvitation.objects.select_for_update().filter(
        account_id=user_id,
    ).order_by("pk"))
    users = {row.pk: row for row in User.objects.select_for_update().filter(
        pk__in={user_id, *extra_user_ids},
    ).order_by("pk")}
    return users[user_id]
