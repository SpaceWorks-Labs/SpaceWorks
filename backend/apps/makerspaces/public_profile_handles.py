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
def claim_handle(user, value):
    """Claim or change the account's one handle. The handle belongs to the ACCOUNT (305c).

    It resolves through `user` to the account profile, so no per-membership profile is needed;
    the legacy `profile` pointer on an old claim is left exactly as it was.
    """
    require_member_account(user)
    from django.contrib.auth import get_user_model

    handle = normalize_handle(value)
    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    current = PublicHandle.objects.filter(user_id=user.pk).first()
    changing = current is not None
    lock_names(handle, *([current.handle] if current else []))
    now = timezone.now()
    released = PublicHandleRedirect.objects.filter(user_id=user.pk, expires_at__gt=now)
    if not current and released.exists():
        # M16: taking back your OWN released name is always allowed; any other name waits 30 days.
        if not released.filter(handle__iexact=handle).exists():
            raise ValidationError({"handle": gettext("Wait 30 days after releasing a handle before claiming another.")})
        released.filter(handle__iexact=handle).delete()
    if current and current.handle == handle:
        return current
    if current and now < current.changed_at + HANDLE_COOLDOWN:
        raise ValidationError({"handle": gettext("Handles can be changed once every 30 days.")})
    if not name_available(handle, now=now) and (not current or current.handle != handle):
        raise ValidationError({"handle": gettext("This name is unavailable.")})
    PublicHandleRedirect.objects.filter(handle__iexact=handle, expires_at__lte=now).delete()
    try:
        with transaction.atomic():
            if current:
                _retire(current, now)
                current.handle, current.changed_at = handle, now
                current.save(update_fields=["handle", "changed_at"])
            else:
                current = PublicHandle.objects.create(user=user, handle=handle, changed_at=now)
    except IntegrityError as exc:
        raise ValidationError({"handle": gettext("This name is unavailable.")}) from exc
    audit.record(user, "member.public_handle_claimed", target=user, meta={"changed": changing})
    _invalidate(user)
    return current


def _slug(text):
    return re.sub(r"[^a-z0-9._-]+", "-", str(text or "").lower()).strip("-._")[:26]


_PLACEHOLDER = re.compile(r"^member_[0-9a-f]{32}$")


def username_is_login(user):
    """Decision 336d (SECURITY-REVIEW M15): login and public handle stay separable.

    A username is a sign-in identifier exactly when the account has a password to go with it. Such a
    username is never suggested to or claimed for its owner automatically -- the profile would
    otherwise publish a list of sign-in names. Accounts that cannot sign in with a password (social,
    OTP or invitation-only) keep decision 308's username-first default. Anyone may still CHOOSE it.
    """
    return bool(user.has_usable_password())


def suggestion_candidates(*, username="", display_name="", pk=0):
    """Decision 308: account username -> display-name slug -> slug + digits (best first).

    A generated placeholder username (`member_<hex>`) is not a name anyone chose, so it is skipped;
    callers drop a sign-in username before calling (`username_is_login`).
    """
    username = (username or "").lower()
    if username and not _PLACEHOLDER.match(username):
        yield username
    base = _slug(display_name) or "member"
    if len(base) < 3:
        base = (base + "-user")[:26]
    yield base
    for number in range(12):
        yield f"{base}{(pk * 7 + number * 13) % 1000 + number}"[:30]


def check_handle(value, *, now=None):
    """`(ok, reason)`; reason is `invalid`, `taken` or ''. No locks: advisory only.

    Decision 336d: only available / taken. A reserved name answers "taken" like a claimed one, so the
    answer never distinguishes a platform word from a person's name.
    """
    value = str(value or "").lower()
    if not re.fullmatch(HANDLE_PATTERN, value):
        return False, "invalid"
    if value in RESERVED_SEGMENTS:
        return False, "taken"
    return (True, "") if name_available(value, now=now) else (False, "taken")


def suggest_handle(*, username="", display_name="", pk=0):
    """The first candidate that is valid and free, or None (never a reserved or taken name)."""
    for candidate in suggestion_candidates(username=username, display_name=display_name, pk=pk):
        if check_handle(candidate)[0]:
            return candidate
    return None


def suggestion_for(user):
    return suggest_handle(username="" if username_is_login(user) else user.username,
                          display_name=user.display_name or user.get_full_name(), pk=user.pk or 0)


def has_handle(user):
    return PublicHandle.objects.filter(user_id=user.pk).exists()


def claim_for_signup(user, handle=None, *, username_only=False):
    """Claim the account's handle INSIDE the caller's account-creation transaction (decision 308).

    A chosen `handle` is validated under the namespace lock and a failure raises, rolling the
    whole sign-up back (the caller must wrap this in the creation transaction). With no `handle`
    the best suggestion is claimed. Either way the first later change is free (no 30-day wait):
    the person had no real chance to deliberate over an automatic pick.
    """
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    now = timezone.now()
    chosen = handle is not None
    username = "" if username_is_login(user) else user.username
    candidates = [handle] if chosen else list(suggestion_candidates(
        username=username, display_name=user.display_name or user.get_full_name(), pk=user.pk))
    if username_only:
        # Existing accounts (decision 308c): only the username is ever claimed for them silently, and
        # never a sign-in username (336d) -- those choose at the blocking step instead.
        candidates = [c for c in candidates[:1] if username and c == username.lower()]
    for candidate in candidates:
        try:
            value = normalize_handle(candidate)
        except ValidationError:
            if chosen:
                raise
            continue
        lock_names(value)
        if not name_available(value, now=now):
            if chosen:
                raise ValidationError({"handle": gettext("This name is unavailable.")})
            continue
        try:
            with transaction.atomic():
                claim = PublicHandle.objects.create(
                    user=user, handle=value, changed_at=now - HANDLE_COOLDOWN)
        except IntegrityError:
            if chosen:
                raise ValidationError({"handle": gettext("This name is unavailable.")})
            continue
        audit.record(user, "member.public_handle_claimed", target=user,
                     meta={"changed": False, "default": not chosen})
        _invalidate(user)
        return claim
    return None


@transaction.atomic
def claim_default_handle(user):
    """Auto-claim a handle for an existing account (profile creation, the migration backfill).

    None when one exists, when the account deliberately released one (a live redirect row), or when
    the username is not valid and free (decision 308c): everyone else sees the blocking step.
    """
    require_member_account(user)
    from django.contrib.auth import get_user_model

    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    now = timezone.now()
    if (PublicHandle.objects.filter(user_id=user.pk).exists()
            or PublicHandleRedirect.objects.filter(user_id=user.pk, expires_at__gt=now).exists()):
        return None
    return claim_for_signup(user, username_only=True)


def claim_requested_handle(user, requested):
    """M14: claim a new sign-up's chosen username once its email is confirmed.

    The name was only grammar-checked at sign-up and may have been taken since; then the best
    suggestion is claimed instead (the first change is free, see `claim_for_signup`). An account that
    already has a handle keeps it.
    """
    if has_handle(user):
        return None
    if requested:
        try:
            with transaction.atomic():
                return claim_for_signup(user, requested)
        except ValidationError:
            pass
    return claim_for_signup(user)


def in_release_cooldown(user, *, now=None):
    """True while a handle this account released itself is still reserved (the 30-day wait, M16)."""
    return PublicHandleRedirect.objects.filter(user_id=user.pk, expires_at__gt=now or timezone.now()).exists()


def ensure_default_handle(user):
    """Decision 308(c) backfill; since 336d never a sign-in username (see `username_is_login`).

    Called in bulk by `manage.py claim_default_handles`, which the updater runs once after migrating to
    0.12.0 (the 308(c) "migration" step). True when the account has a handle afterwards.
    """
    if has_handle(user):
        return True
    if (getattr(user, "account_kind", None) != "member" or user.retired_at is not None
            or getattr(user, "merged_into_id", None) is not None or getattr(user, "is_walk_in", False)):
        return False
    claim_default_handle(user)
    return has_handle(user)


def _retire(current, now):
    PublicHandleRedirect.objects.update_or_create(handle=current.handle, defaults={
        "user_id": current.user_id, "profile_id": current.profile_id,
        "makerspace_id": current.makerspace_id, "organization_id": current.organization_id,
        "released_at": now, "expires_at": now + HANDLE_RELEASE_DELAY,
    })


def _invalidate(user):
    from .public_profile_cache import invalidate_account
    invalidate_account(user.pk)


@transaction.atomic
def release_handle(user):
    from django.contrib.auth import get_user_model
    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    current = PublicHandle.objects.filter(user_id=user.pk).first()
    if current:
        lock_names(current.handle)
        _retire(current, timezone.now())
        legacy_id = current.profile_id
        current.delete()
        # Reclaiming later must require a new publication act, on the account and any legacy row.
        from .models_account_profile import AccountProfile
        from .models_profiles import MemberProfile
        AccountProfile.objects.filter(user_id=user.pk).update(public_visible=False, public_consented_at=None)
        MemberProfile.objects.filter(pk=legacy_id).update(public_visible=False, public_consented_at=None)
        _invalidate(user)
        audit.record(user, "member.public_handle_released", target=user, meta={})
