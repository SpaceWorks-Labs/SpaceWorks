"""Account erasure synchronization for independent tenant DOB evidence."""

from django.utils.translation import gettext
from apps.encryption.account_models import PiiAccountWriteFence
from apps.encryption.account_write_fence import assert_account_fence_held
from apps.events.contracts.providers import LockedContext

from .errors import DerivationError


def require_owner_fence(subject, locks):
    """The outer service acquires this shared fence before any event row lock.

    No account key/fence row is created here. An owner who never used Saved
    details needs only the advisory lock; persistent erase/closed state refuses.
    """
    if not isinstance(locks, LockedContext) or subject.owner_member_id not in locks.account_ids:
        raise RuntimeError("Declare the source owner's account fence before event locks.")
    assert_account_fence_held(subject.owner_member_id)
    state = PiiAccountWriteFence.objects.filter(user_id=subject.owner_member_id).values_list("state", flat=True).first()
    if state is not None and state != PiiAccountWriteFence.State.OPEN:
        raise DerivationError("account_key_changed", gettext("Account key changed."), status=409)
