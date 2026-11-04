"""Account ownership never derives from a tenant membership or staff grant."""
from django.contrib.auth import get_user_model

from apps.accounts.staff_identity import is_person

from .errors import SavedDetailsError


def require_owner(actor_id, *, lock=False):
    users = get_user_model().objects
    if lock:
        users = users.select_for_update()
    user = users.filter(pk=actor_id).first()
    if not user or not user.is_active or not is_person(user) or (
        user.access_status != "active" or user.is_walk_in or user.is_tenant_dump_stub or user.retired_at is not None
    ):
        raise SavedDetailsError("permission_denied", "Use an active member account.", 403)
    return user


def owner_read_gate(actor_id):
    """Prepare key custody once outside locks, then recheck revocation per chunk.

    The returned closure performs only nonlocking DB reads. It never unwraps a
    key or calls KMS while a private stream or event asset copy is in progress.
    """
    from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
    from apps.encryption.account_services import AccountKeyUnavailable, get_account_key

    require_owner(actor_id)
    prepared = get_account_key(actor_id)
    epoch, version = prepared.epoch, prepared.version

    def authorize():
        require_owner(actor_id)
        if not PiiAccountWriteFence.objects.filter(
            user_id=actor_id, state="open", epoch=epoch,
        ).exists() or not AccountPiiKey.objects.filter(
            user_id=actor_id, version=version, status="active",
        ).exists():
            raise AccountKeyUnavailable("Account key unavailable.")

    authorize()
    return authorize
