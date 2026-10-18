"""Typed namespace lifecycle. Caller holds owner/authority/page locks first.

Member lock order remains account -> sorted names -> membership. Tenant/global
page actions take tenant/org -> account -> authority -> page -> sorted names.
Imports must take the same owner locks before calling the shared name locks.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from .models_profiles import PublicHandle, PublicHandleRedirect
from .public_profile_handles import (
    HANDLE_COOLDOWN, normalize_handle, lock_names, name_available, _retire,
)
from .public_page_errors import PageConflict


def owner_filter(kind, owner):
    if kind not in {"makerspace", "organization"}:
        raise ValueError("Typed owner required.")
    return {f"{kind}_id": owner.pk}


def claim_locked(kind, owner, value):
    if not isinstance(value, str):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"handle": "Provide a handle string."})
    handle = normalize_handle(value)
    query = owner_filter(kind, owner)
    current = PublicHandle.objects.filter(**query).first()
    lock_names(handle, *([current.handle] if current else []))
    now = timezone.now()
    if current and current.handle == handle:
        return current
    if ((current and now < current.changed_at + HANDLE_COOLDOWN)
            or (not current and PublicHandleRedirect.objects.filter(**query, expires_at__gt=now).exists())):
        raise PageConflict("handle_cooldown", "Wait 30 days before changing or reclaiming a handle.")
    if not name_available(handle, now=now):
        raise PageConflict("handle_unavailable", "This name is unavailable.")
    PublicHandleRedirect.objects.filter(handle__iexact=handle, expires_at__lte=now).delete()
    try:
        with transaction.atomic():
            if current:
                _retire(current, now)
                current.handle, current.changed_at = handle, now
                current.save(update_fields=["handle", "changed_at"])
            else:
                current = PublicHandle.objects.create(**query, handle=handle, changed_at=now)
    except IntegrityError as exc:
        raise PageConflict("handle_unavailable", "This name is unavailable.") from exc
    return current


def release_locked(kind, owner, page):
    current = PublicHandle.objects.filter(**owner_filter(kind, owner)).first()
    if current:
        lock_names(current.handle)
        _retire(current, timezone.now())
        current.delete()
    if page is not None:
        page.published_revision = None
        page.save(update_fields=["published_revision"])


def suggestion(kind, owner):
    from rest_framework.exceptions import ValidationError
    candidates = [owner.slug]
    number, encoded = owner.pk, ""
    while number:
        number, digit = divmod(number, 36)
        encoded = "0123456789abcdefghijklmnopqrstuvwxyz"[digit] + encoded
    base = f"{'space' if kind == 'makerspace' else 'org'}-{encoded or '0'}"[:27]
    candidates += [base] + [f"{base}-{n}" for n in range(1, 20)]
    for value in candidates:
        try:
            value = normalize_handle(value)
        except ValidationError:
            continue
        if name_available(value):
            return value
    return None
