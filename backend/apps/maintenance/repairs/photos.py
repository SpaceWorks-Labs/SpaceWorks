"""Issue photo uploads: a presign bound to its uploader, attached exactly once.

The presign answer carries a signed grant naming the space, the object key and the
uploader (an account, or an account-less borrower's verified-email fingerprint). An
issue only accepts photos whose grant names the same uploader, so nobody can attach
someone else's upload, and a key can back one photo row only.
"""

from django.utils.translation import gettext
from django.core import signing
from rest_framework.exceptions import ValidationError

from . import storage

SALT = "spaceworks.repairs.photo"
MAX_AGE = 60 * 60
MAX_PER_STEP = 6


def owner_for_user(user):
    return f"user:{user.pk}"


def owner_for_email(key):
    return f"email:{key}"


def issue_upload(space, content_type, owner):
    key = storage.photo_key(space.pk, content_type)
    upload = storage.presign(key, content_type)
    grant = signing.dumps({"m": space.pk, "k": key, "o": owner}, salt=SALT)
    return {"photo_token": grant, "upload": upload, "max_bytes": storage.max_bytes()}


def _keys(space, tokens, owner):
    if not isinstance(tokens, (list, tuple)) or len(tokens) > MAX_PER_STEP:
        raise ValidationError({"photos": gettext('Attach at most {MAX_PER_STEP} photos at a time.').format(MAX_PER_STEP=MAX_PER_STEP)})
    keys = []
    for token in tokens:
        try:
            data = signing.loads(str(token), salt=SALT, max_age=MAX_AGE)
        except signing.BadSignature:
            raise ValidationError({"photos": gettext("A photo upload has expired; upload it again.")})
        if (not isinstance(data, dict) or data.get("m") != space.pk or data.get("o") != owner
                or not storage.owns_key(data.get("k"), space.pk)):
            raise ValidationError({"photos": gettext("A photo upload does not belong to you.")})
        keys.append(data["k"])
    if len(set(keys)) != len(keys):
        raise ValidationError({"photos": gettext("The same photo was attached twice.")})
    return keys


def validate(space, tokens, owner):
    """Promote and check every upload BEFORE the issue transaction takes its locks."""
    from apps.maintenance.models import IssuePhoto
    keys = _keys(space, tokens or [], owner)
    if keys and IssuePhoto.objects.filter(object_key__in=keys).exists():
        raise ValidationError({"photos": gettext("A photo is already attached.")})
    return [(key, *storage.validated_photo(key)) for key in keys]


def attach(issue, validated, stage, uploader):
    """Inside the issue transaction: charge managed storage, then one row per photo."""
    from apps.maintenance.models import IssuePhoto
    from apps.makerspaces import limits
    rows = []
    for key, size, content_type in validated:
        limits.add_storage(issue.makerspace, size)
        rows.append(IssuePhoto.objects.create(issue=issue, stage=stage, object_key=key, size_bytes=size,
                                              content_type=content_type, uploaded_by=uploader))
    return rows
