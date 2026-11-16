"""Possession-bound Firebase browser registration, independent of analytics."""
import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.audit.services import record
from config.redis_cache import SharedCacheUnavailable, claim_once
from apps.integrations.push_firebase_browser import send_challenge
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import tenant_write
from .models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from django.utils.translation import gettext

TTL = 300


def _mac(purpose, *values):
    message = "\x00".join((purpose, *(str(value) for value in values))).encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _key(purpose, challenge):
    return f"browser-firebase:{purpose}:{_mac(purpose, challenge)}"


def begin(*, actor, space, project, fid, challenge, push_settings):
    identity = _mac("fid", project, fid)
    dedupe = f"browser-firebase:dedupe:{_mac('dedupe', actor.pk, space.pk, identity)}"
    if not cache.add(dedupe, "1", timeout=TTL):
        raise Throttled(wait=TTL)
    nonce = secrets.token_urlsafe(32)
    digest = _mac("proof", challenge, nonce, actor.pk, space.pk, project, fid)
    key = _key("proof", challenge)
    if not cache.add(key, digest, timeout=TTL):
        raise ValidationError(gettext("Challenge is already in use."))
    try:
        send_challenge(push_settings, project, fid, challenge, nonce)
    except Exception:
        cache.delete(key)
        raise
    return {"challenge": challenge}


def confirm(*, actor, space, project, fid, challenge, nonce):
    key = _key("proof", challenge)
    supplied = cache.get(key)
    if not isinstance(supplied, str):
        raise ValidationError(gettext("Challenge is invalid or expired."))
    # Each slot is a fresh atomic add and lives at least as long as the proof.
    # The per-proof HMAC changes on reissue, avoiding expired-slot reuse races.
    claimed = any(cache.add(_key(f"attempt-{index}", supplied), "1", timeout=TTL) for index in range(5))
    if not claimed:
        raise Throttled(wait=TTL)
    expected = _mac("proof", challenge, nonce, actor.pk, space.pk, project, fid)
    if not hmac.compare_digest(supplied, expected):
        raise ValidationError(gettext("Challenge is invalid or expired."))
    try:  # single-use even while Redis is down: never claimed in one worker only (decision 339)
        fresh = claim_once(_key("used", supplied), TTL, value="1")
    except SharedCacheUnavailable:
        raise Throttled(wait=5, detail=gettext("Confirmation is briefly unavailable. Retry shortly.")) from None
    if not fresh:
        raise ValidationError(gettext("Challenge was already used."))
    identity = _mac("fid", project, fid)
    with tenant_write(space.pk), transaction.atomic():
        Makerspace.objects.select_for_update().get(pk=space.pk)
        owner, _ = BrowserFirebaseInstallation.objects.get_or_create(fid_hmac=identity, defaults={"user": actor})
        owner = BrowserFirebaseInstallation.objects.select_for_update().get(pk=owner.pk)
        if owner.user_id != actor.pk:
            owner.user = actor
            owner.owner_epoch = uuid.uuid4()
            owner.save(update_fields=["user", "owner_epoch", "updated_at"])
        rows = BrowserFirebaseRegistration.objects.filter(makerspace=space, project_id=project, fid_hmac=identity)
        rows.exclude(user=actor).filter(active=True).update(active=False, revoked_at=timezone.now())
        row, _ = rows.get_or_create(user=actor, makerspace=space, project_id=project, fid_hmac=identity)
        row.set_fid(fid)
        row.active, row.confirmed_at, row.revoked_at = True, timezone.now(), None
        row.save(update_fields=["fid_ciphertext", "active", "confirmed_at", "revoked_at"])
        record(actor, "notification.browser_firebase_subscribed", makerspace=space, target=space)
    cache.delete(key)
    return {"owner_epoch": str(owner.owner_epoch)}
