"""Avatar and project images of the account-level profile, on the shared public-image bucket.

One `member` image kind covers both. The bucket key still carries a makerspace id
(`member/<space_id>/...`) because storage accounting and the key-collision rule are per space:
an upload is charged to the space whose namespace it was minted in (the caller's home space, or
the path space of a legacy route). The profile itself is account-level, so a key may outlive the
space that minted it -- `space_for_key` returns None then and the release path just deletes the
object without touching a quota that no longer exists.

A key must never be attachable to a second holder, or clearing either blanks the other.
"""

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.inventory import public_image_storage
from apps.makerspaces import limits

IMAGE_KIND = "member"
# [auto, 243] A membership-less account has no home space to mint `member/<space_id>/...` in, so its
# profile images live under `account/<user_id>/...`. Such a key belongs to the account, not to a
# tenant: it is never charged to any space quota, never collected by a space purge or the storage
# reconciler, and is deleted by `account_profile_purge`. Existing `member/<space_id>/` keys keep working.
ACCOUNT_KIND = "account"


def account_key_prefix(user):
    return f"{ACCOUNT_KIND}/{user.pk}/"


def is_account_key(object_key):
    return (object_key or "").startswith(f"{ACCOUNT_KIND}/")


def space_for_key(object_key):
    """The makerspace whose namespace minted this key, or None (purged space, foreign key)."""
    from apps.makerspaces.models import Makerspace

    parts = (object_key or "").split("/")
    if len(parts) < 3 or parts[0] != IMAGE_KIND or not parts[1].isdigit():
        return None
    return Makerspace.objects.filter(pk=int(parts[1])).first()


def home_space(user):
    """The space an account-level upload is minted in: the newest active, servable membership."""
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.servability import servable_q

    row = (MakerspaceMembership.all_tracks.filter(user=user, status="active")
           .filter(servable_q("makerspace")).select_related("makerspace")
           .order_by("-activated_at", "-pk").first())
    return row.makerspace if row else None


def _release(old_key):
    old_space = space_for_key(old_key)
    if old_space is not None:
        public_image_storage.release_public_image_on_commit(old_space, old_key)
    else:
        transaction.on_commit(lambda: public_image_storage.delete_object(old_key))


def _swap(profile, holder, field, object_key, *, project=None):
    # HEADed before any lock is taken: an S3 round trip under a row lock is lock contention.
    new_size = public_image_storage.object_size(object_key) if object_key else 0
    # One lock on the PROFILE serialises its avatar against its own projects' images, because
    # every member-kind key belongs to exactly one account profile.
    profile = type(profile).objects.select_for_update().get(pk=profile.pk)
    holder = type(holder).objects.select_for_update().get(pk=holder.pk)
    old_key = getattr(holder, field)
    if object_key == old_key:
        return holder
    space = space_for_key(object_key) if object_key else None
    if object_key and public_image_storage.public_image_key_in_use(
        space.pk if space else 0, object_key,
        account_profile_id=None if project else profile.pk,
        account_project_id=project.pk if project else None,
    ):
        raise ValidationError({"object_key": gettext("This image is already in use.")})
    if object_key and space is not None:
        limits.add_storage(space, new_size or 0)
    if old_key:
        _release(old_key)
    setattr(holder, field, object_key)
    holder.save(update_fields=[field, "updated_at"])
    return holder


@transaction.atomic
def set_avatar(profile, object_key, *, makerspace=None):
    result = _swap(profile, profile, "avatar_key", object_key)
    from .account_profile import mirror_avatar
    mirror_avatar(profile.user, object_key)
    _audit_image(profile.user, "avatar", None, object_key, makerspace)
    return result


@transaction.atomic
def set_project_image(profile, project, object_key, *, makerspace=None):
    result = _swap(profile, project, "image_key", object_key, project=project)
    _audit_image(profile.user, "project", project.pk, object_key, makerspace)
    return result


def _audit_image(user, kind, project_id, object_key, makerspace):
    """Attaching and clearing member imagery are state changes and are recorded.

    The object key is deliberately NOT logged: the audit log is append-only, so a key written
    here outlives the image and every row that could name it.
    """
    audit.record(
        user, "member.profile_image_cleared" if not object_key else "member.profile_image_updated",
        makerspace=makerspace, target=user, meta={"kind": kind, "project_id": project_id},
    )


def clear_project_image(profile, project):
    """Release a project's image without deleting the row (also used when a project is removed)."""
    if project.image_key:
        set_project_image(profile, project, "")
