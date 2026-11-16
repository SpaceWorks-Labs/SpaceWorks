"""Which provider serves a space, and saving / describing / testing the settings (platform and per space).

A space's own complete provider wins; otherwise the platform's serves it unless the space opted out. Secrets are
write-only: `describe` never returns one, only "configured", the URL and a short public fingerprint. Every save,
rotation, removal and test writes one audit row naming the scope and the fingerprint, never a secret.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from ..models_image_adapter import MakerspaceImageAdapter, PlatformImageAdapter
from . import client, url_policy
from .client import ProviderConfig
from .errors import AdapterError

MIN_SECRET = 16


def space_row(makerspace, *, create=False):
    row = MakerspaceImageAdapter.objects.filter(makerspace=makerspace).first()
    return row or (MakerspaceImageAdapter(makerspace=makerspace) if create else None)


def platform_row(*, create=False):
    row = PlatformImageAdapter.objects.filter(pk=1).first()
    return row or (PlatformImageAdapter() if create else None)


def _config(row, scope):
    return ProviderConfig(url=row.provider_url, secret=row.get_secret(), scope=scope)


def resolve(makerspace):
    """-> ProviderConfig of the provider serving this space, or None."""
    own = space_row(makerspace)
    if own is not None and own.complete:
        return _config(own, "space")
    shared = platform_row()
    if shared is not None and shared.complete and (own is None or own.use_platform_provider):
        return _config(shared, "platform")
    return None


def configured(makerspace):
    return resolve(makerspace) is not None


def _public(row):
    if row is None:
        return {"configured": False, "provider_url": "", "fingerprint": "", "last_test_at": None,
                "last_test_ok": None, "last_test_error": ""}
    return {"configured": row.complete, "provider_url": row.provider_url, "fingerprint": row.secret_fingerprint,
            "last_test_at": row.last_test_at, "last_test_ok": row.last_test_ok, "last_test_error": row.last_test_error}


def describe_platform():
    return _public(platform_row())


def describe_space(makerspace):
    row = space_row(makerspace)
    effective = resolve(makerspace)
    return {**_public(row), "use_platform_provider": True if row is None else row.use_platform_provider,
            "platform_available": bool(platform_row() and platform_row().complete),
            "effective": effective.scope if effective else None}


def _record(actor, row, scope, makerspace, action, extra=None):
    audit.record(actor, action, makerspace=makerspace, target=row,
                 meta={"scope": scope, "fingerprint": row.secret_fingerprint, **(extra or {})})


def save(actor, row, data, *, scope, makerspace=None):
    """Apply `provider_url`, `secret`, `clear` and (space only) `use_platform_provider`; audit each change."""
    events = []
    with transaction.atomic():
        if data.get("clear"):
            if row.complete:
                events.append(("image_adapter.removed", None))
            row.clear()
        elif data.get("provider_url") or data.get("secret"):
            url = url_policy.clean_base_url(data.get("provider_url") or row.provider_url, scope=scope)
            secret = data.get("secret") or ""
            if secret and len(secret) < MIN_SECRET:
                raise ValidationError({"secret": gettext("The shared secret needs at least 16 characters.")})
            if not secret and not row.secret:
                raise ValidationError({"secret": gettext("Enter the shared secret the provider verifies requests with.")})
            if not secret and row.provider_url and url != row.provider_url:
                # The saved secret belongs to the old provider: a new address must come with its own secret, or
                # changing the address would hand signed requests (and photos) to whoever answers there.
                raise ValidationError({"secret": gettext("Enter the shared secret again when you change the address.")})
            was_complete, previous = row.complete, row.secret_fingerprint
            row.provider_url = url
            if secret:
                row.set_secret(secret)
            row.last_test_at, row.last_test_ok, row.last_test_error = None, None, ""
            events.append(("image_adapter.rotated" if was_complete and secret and row.secret_fingerprint != previous
                           else "image_adapter.saved", None))
        switch = data.get("use_platform_provider")
        if switch is not None and scope == "space" and switch != row.use_platform_provider:
            row.use_platform_provider = switch
            events.append(("image_adapter.platform_switch", {"use_platform_provider": bool(switch)}))
        row.save()
        for action, extra in events:
            _record(actor, row, scope, makerspace, action, extra)
    return row


def test(actor, row, *, scope, makerspace=None):
    """Signed health check against the SAVED settings; records and audits the outcome."""
    if not row.complete:
        raise ValidationError({"detail": gettext("Save the provider's address and secret first.")})
    outcome = "ok"
    try:
        client.test_connection(_config(row, scope))
    except AdapterError as exc:
        outcome = exc.code
    row.last_test_at, row.last_test_ok, row.last_test_error = timezone.now(), outcome == "ok", "" if outcome == "ok" else outcome
    row.save(update_fields=["last_test_at", "last_test_ok", "last_test_error", "updated_at"])
    _record(actor, row, scope, makerspace, "image_adapter.tested", {"outcome": outcome})
    return {"ok": outcome == "ok", "error": "" if outcome == "ok" else outcome, "tested_at": row.last_test_at}
