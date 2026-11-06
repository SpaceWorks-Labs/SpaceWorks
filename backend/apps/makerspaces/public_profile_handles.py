"""Transactional namespace lifecycle. The same locks are used by portable imports."""

from django.utils.translation import gettext
from apps.accounts.account_kind_guards import require_member_account

import hashlib
import re
from datetime import timedelta

from django.db import connection, transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from .models_profiles import HANDLE_PATTERN, PublicHandle, PublicHandleRedirect
from .public_profile_reserved import RESERVED_SEGMENTS

HANDLE_COOLDOWN = timedelta(days=30)
HANDLE_RELEASE_DELAY = timedelta(days=30)


def normalize_handle(value):
    value = str(value).lower()
    if not re.fullmatch(HANDLE_PATTERN, value):
        raise ValidationError({"handle": gettext("Use 3–30 letters, numbers, dots, underscores or hyphens; start and end with a letter or number.")})
    if value in RESERVED_SEGMENTS:
        raise ValidationError({"handle": gettext("This name is reserved.")})
    return value


def lock_names(*names):
    # Cross-table exclusion (current claims + retired reservations), including first
    # claims with no row to lock. Stable order prevents rename deadlocks.
    for name in sorted(set(names)):
        key = int.from_bytes(hashlib.sha256(name.lower().encode()).digest()[:8], "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def name_available(handle, *, now=None):
    now = now or timezone.now()
    return not (PublicHandle.objects.filter(handle__iexact=handle).exists()
                or PublicHandleRedirect.objects.filter(handle__iexact=handle, expires_at__gt=now).exists())


@transaction.atomic
def claim_handle(membership, value):
    require_member_account(membership.user)
    from django.contrib.auth import get_user_model
    from .profile_services import profile_for

    handle = normalize_handle(value)
    get_user_model().objects.select_for_update(no_key=True).get(pk=membership.user_id)
    current = PublicHandle.objects.filter(user_id=membership.user_id).first()
    changing = current is not None
    previous_profile_id = current.profile_id if current else None
    lock_names(handle, *([current.handle] if current else []))
    now = timezone.now()
    if not current and PublicHandleRedirect.objects.filter(
        user_id=membership.user_id, expires_at__gt=now,
    ).exists():
        raise ValidationError({"handle": gettext("Wait 30 days after releasing a handle before claiming another.")})
    if current and current.handle == handle and current.profile.membership_id == membership.pk:
        return current
    if current and now < current.changed_at + HANDLE_COOLDOWN:
        raise ValidationError({"handle": gettext("Handles can be changed once every 30 days.")})
    if not name_available(handle, now=now) and (not current or current.handle != handle):
        raise ValidationError({"handle": gettext("This name is unavailable.")})
    PublicHandleRedirect.objects.filter(handle__iexact=handle, expires_at__lte=now).delete()
    from .models import MakerspaceMembership
    MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
    profile = profile_for(membership)
    try:
        with transaction.atomic():
            if current:
                old = current.handle
                if old != handle:
                    _retire(current, now)
                current.handle, current.profile, current.changed_at = handle, profile, now
                current.save(update_fields=["handle", "profile", "changed_at"])
            else:
                current = PublicHandle.objects.create(user=membership.user, profile=profile,
                                                     handle=handle, changed_at=now)
    except IntegrityError as exc:
        raise ValidationError({"handle": gettext("This name is unavailable.")}) from exc
    audit.record(membership.user, "member.public_handle_claimed", makerspace=membership.makerspace,
                 target=membership, meta={"changed": changing})
    from .public_profile_cache import invalidate_profile
    invalidate_profile(profile.pk)
    if previous_profile_id and previous_profile_id != profile.pk:
        invalidate_profile(previous_profile_id)
    return current


def _retire(current, now):
    PublicHandleRedirect.objects.update_or_create(handle=current.handle, defaults={
        "user_id": current.user_id, "profile_id": current.profile_id,
        "makerspace_id": current.makerspace_id, "organization_id": current.organization_id,
        "released_at": now, "expires_at": now + HANDLE_RELEASE_DELAY,
    })


@transaction.atomic
def release_handle(membership):
    from django.contrib.auth import get_user_model
    get_user_model().objects.select_for_update(no_key=True).get(pk=membership.user_id)
    current = PublicHandle.objects.filter(user_id=membership.user_id,
                                         profile__membership=membership).first()
    if current:
        lock_names(current.handle)
        _retire(current, timezone.now())
        profile = current.profile
        current.delete()
        # Reclaiming later must require a new publication act.
        type(profile).objects.filter(pk=profile.pk).update(public_visible=False, public_consented_at=None)
        from .public_profile_cache import invalidate_profile
        invalidate_profile(profile.pk)
        audit.record(membership.user, "member.public_handle_released", makerspace=membership.makerspace,
                     target=membership, meta={})
