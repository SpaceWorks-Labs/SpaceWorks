"""Delete a purged account's global profile and its public images (decision 305)."""

from django.db import transaction
from django.utils import timezone

from apps.inventory import public_image_storage

from .models_account_profile import AccountProfile, AccountProject
from .models_profiles import PublicHandle


def purge_account_profile(user):
    profile = AccountProfile.objects.filter(user=user).first()
    keys = set()
    if profile is not None:
        keys = {profile.avatar_key, *AccountProject.objects.filter(profile=profile).values_list("image_key", flat=True)}
        profile.delete()  # children cascade
    # The handle is the person's public name. It is NOT freed at once (SECURITY-REVIEW L-P2): it is
    # retired into the same 30-day reservation a released handle gets, so nobody can take over a
    # purged person's address while links, share cards and caches still point at it. The redirect
    # leads nowhere (the account has no profile any more) and lapses like any other.
    from .public_profile_handles import _retire, lock_names

    current = PublicHandle.objects.filter(user=user).first()
    if current is not None:
        lock_names(current.handle)
        _retire(current, timezone.now())
        current.delete()
    for key in keys - {""}:
        from .profile_images import space_for_key
        space = space_for_key(key)  # None for an `account/<user_id>/` key: nothing was charged
        if space is not None:
            public_image_storage.release_public_image_on_commit(space, key)
        else:
            transaction.on_commit(lambda key=key: public_image_storage.delete_object(key))


def without_account_held(keys):
    """Drop keys an account-level profile still references (decision 305).

    Migrated avatars and project images are SHARED between a legacy per-membership row and the
    account row, so purging the legacy owner's space must not delete an object the person's global
    profile still shows. The account row, not the space, now owns the object.
    """
    keys = [key for key in keys if key]
    if not keys:
        return []
    held = set(AccountProfile.objects.filter(avatar_key__in=keys).values_list("avatar_key", flat=True))
    held |= set(AccountProject.objects.filter(image_key__in=keys).values_list("image_key", flat=True))
    return [key for key in keys if key not in held]
