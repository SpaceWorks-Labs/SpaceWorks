"""Save, rotate, remove and describe wallet-pass credentials (decision 223(l)).

One code path for the two scopes: a makerspace row (Space Manager) and the platform singleton
(superadmin). Secrets are write-only: `describe` returns only "configured", the public
identifiers, the certificate fingerprint and its expiry. Every save, rotation and removal
writes one audit row naming the scope, the platform (apple/google) and the PUBLIC fingerprint,
never a secret. A partial update keeps the stored secrets the request did not replace.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from ..models import MakerspaceWalletCredentials, PlatformWalletCredentials
from . import credential_parsing as parsing
from .credentials import apple_for, google_for

APPLE_INPUTS = ("apple_p12", "apple_cert_pem", "apple_key_pem", "apple_wwdr_pem", "apple_pass_type_id",
                "apple_team_id")
GOOGLE_INPUTS = ("google_issuer_id", "google_class_prefix", "google_service_account")


def space_row(makerspace, *, create=False):
    row = MakerspaceWalletCredentials.objects.filter(makerspace=makerspace).first()
    if row is None and create:
        row = MakerspaceWalletCredentials(makerspace=makerspace)
    return row


def platform_row(*, create=False):
    row = PlatformWalletCredentials.objects.filter(pk=1).first()
    return row or (PlatformWalletCredentials() if create else None)


def _group(row, name):
    """(public fields) of one platform group, never a secret."""
    if row is None:
        return {"configured": False}
    if name == "apple":
        soon = (row.apple_cert_expires_at is not None
                and row.apple_cert_expires_at <= timezone.now() + timedelta(days=parsing.EXPIRY_WARNING_DAYS))
        return {"configured": row.apple_complete, "pass_type_id": row.apple_pass_type_id, "team_id": row.apple_team_id,
                "fingerprint": row.apple_cert_fingerprint, "expires_at": row.apple_cert_expires_at,
                "expires_soon": bool(row.apple_complete and soon)}
    return {"configured": row.google_complete, "issuer_id": row.google_issuer_id,
            "class_prefix": row.google_class_prefix, "fingerprint": row.google_key_fingerprint}


def describe(row):
    return {"apple": _group(row, "apple"), "google": _group(row, "google")}


def describe_space(makerspace):
    """What the space entered, plus which source actually signs its passes (None = feature off)."""
    apple, google = apple_for(makerspace), google_for(makerspace)
    row = space_row(makerspace)
    return {**describe(row), "use_platform_credentials": True if row is None else row.use_platform_credentials,
            "effective": {"apple": apple.source if apple else None, "google": google.source if google else None}}


def _record(actor, row, scope, makerspace, action, platform, fingerprint):
    audit.record(actor, action, makerspace=makerspace, target=row,
                 meta={"scope": scope, "platform": platform, "fingerprint": fingerprint})


def _apply_apple(row, data):
    stored = {"cert": row.secret("apple_cert_pem"), "key": row.secret("apple_key_pem"),
              "wwdr": row.secret("apple_wwdr_pem"), "pass_type_id": row.apple_pass_type_id, "team_id": row.apple_team_id}
    parsed = parsing.parse_apple(data, stored)
    replaced = parsed["fingerprint"] != row.apple_cert_fingerprint
    row.apple_pass_type_id, row.apple_team_id = parsed["pass_type_id"], parsed["team_id"]
    row.set_secret("apple_cert_pem", parsed["cert"])
    row.set_secret("apple_key_pem", parsed["key"])
    row.set_secret("apple_wwdr_pem", parsed["wwdr"])
    row.apple_cert_fingerprint, row.apple_cert_expires_at = parsed["fingerprint"], parsed["expires_at"]
    return replaced, parsed["fingerprint"]


def _apply_google(row, data):
    stored = {"issuer_id": row.google_issuer_id, "class_prefix": row.google_class_prefix,
              "service_account": row.secret("google_service_account")}
    parsed = parsing.parse_google(data, stored)
    replaced = parsed["fingerprint"] != row.google_key_fingerprint
    row.google_issuer_id, row.google_class_prefix = parsed["issuer_id"], parsed["class_prefix"]
    row.set_secret("google_service_account", parsed["service_account"])
    row.google_key_fingerprint = parsed["fingerprint"]
    return replaced, parsed["fingerprint"]


def save(actor, row, data, *, scope, makerspace=None):
    """Apply the submitted groups (and `clear_apple` / `clear_google`) to `row`; audit each change.

    A first save is `wallet_pass.credentials_saved`; replacing a stored certificate or key is
    `credentials_rotated`; clearing a group is `credentials_removed`.
    """
    events = []
    old_pass_type_id = row.apple_pass_type_id
    with transaction.atomic():
        for name, inputs, apply, clear in (("apple", APPLE_INPUTS, _apply_apple, row.clear_apple),
                                           ("google", GOOGLE_INPUTS, _apply_google, row.clear_google)):
            if data.get(f"clear_{name}"):
                fingerprint = getattr(row, f"{name}_cert_fingerprint" if name == "apple" else "google_key_fingerprint")
                if getattr(row, f"{name}_complete"):
                    events.append(("wallet_pass.credentials_removed", name, fingerprint))
                clear()
            elif any(data.get(field) for field in inputs):
                was_complete = getattr(row, f"{name}_complete")
                replaced, fingerprint = apply(row, data)
                events.append(("wallet_pass.credentials_rotated" if was_complete and replaced
                               else "wallet_pass.credentials_saved", name, fingerprint))
        switch = data.get("use_platform_credentials")
        if switch is not None and scope == "space" and switch != row.use_platform_credentials:
            row.use_platform_credentials = switch
            events.append(("wallet_pass.credentials_platform_switch", "wallet", ""))
        row.save()
        for action, name, fingerprint in events:
            _record(actor, row, scope, makerspace, action, name, fingerprint)
    # An Apple pass is bound to its Pass Type ID: passes already in wallets stop verifying when it
    # changes, so holders must re-add them from "My passes". Transient flag, never stored.
    row.reissue_needed = bool(old_pass_type_id and row.apple_pass_type_id != old_pass_type_id)
    return row
