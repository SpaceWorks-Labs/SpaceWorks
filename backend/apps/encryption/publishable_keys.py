"""``public_api_key`` rotation with a grace window (#77, #120).

A publishable key is a public browser credential, not a secret, but a leaked one lets any
origin on the space's allow-list impersonate its public site. Rotating issues a new key at
once; the previous one keeps working for ``PUBLISHABLE_KEY_ROTATION_GRACE_HOURS`` so the
space can redeploy its site, then it is refused. Audited in the space; key values are
never written to the audit log.
"""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .models_rotation import RetiredPublishableKey


def _fingerprint(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def rotate_publishable_key(actor, makerspace):
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.models import generate_publishable_key

    grace = timedelta(hours=max(0, settings.PUBLISHABLE_KEY_ROTATION_GRACE_HOURS))
    with transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        old, new = locked.public_api_key, generate_publishable_key()
        valid_until = timezone.now() + grace
        RetiredPublishableKey.objects.create(makerspace=locked, key=old, valid_until=valid_until)
        Makerspace.objects.filter(pk=locked.pk).update(public_api_key=new)
        audit.record(actor, "makerspace.public_api_key_rotated", makerspace=locked, meta={
            "previous_fingerprint": _fingerprint(old), "current_fingerprint": _fingerprint(new),
            "previous_valid_until": valid_until.isoformat()})
    makerspace.public_api_key = new
    return new, valid_until


def makerspace_id_for_retired_key(key, *, now=None):
    """The space a still-valid retired key belongs to, or ``None`` (expired keys are refused)."""
    if not key:
        return None
    return RetiredPublishableKey.objects.filter(
        key=key, valid_until__gt=now or timezone.now()).values_list("makerspace_id", flat=True).first()
