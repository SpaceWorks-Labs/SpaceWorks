"""Wallet-pass signing credentials: the space's own, else the platform's (decision 223(l)).

Resolution per platform, independently for Apple and Google:
  1. the makerspace's own complete credentials (`MakerspaceWalletCredentials`, encrypted);
  2. the platform credentials the superadmin saved (`PlatformWalletCredentials`, encrypted), on every
     install (decision 240: the fallback never depends on "Hosting other makerspaces");
  3. the deployment files named by `WALLET_*` settings (the operator's original path, Q-I11).
When none is complete the platform is OFF for that space and nothing is shown. Resolution
returns key material to the signing code only; nothing here is ever serialised to a client.
"""
import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class AppleCredentials:
    pass_type_id: str
    team_id: str
    cert_pem: bytes
    key_pem: bytes
    wwdr_pem: bytes
    source: str

    def material(self):
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return (x509.load_pem_x509_certificate(self.cert_pem), load_pem_private_key(self.key_pem, password=None),
                x509.load_pem_x509_certificate(self.wwdr_pem))


@dataclass(frozen=True)
class GoogleCredentials:
    issuer_id: str
    class_prefix: str
    client_email: str
    private_key: str
    source: str

    @property
    def class_id(self):
        return f"{self.issuer_id}.{self.class_prefix}"


def _file(name):
    value = getattr(settings, name, "") or ""
    return Path(value) if value and Path(value).is_file() else None


def _space_row(makerspace):
    from ..models import MakerspaceWalletCredentials
    if makerspace is None:
        return None
    pk = getattr(makerspace, "pk", makerspace)
    return MakerspaceWalletCredentials.objects.filter(makerspace_id=pk).first()


def _platform_row():
    from ..models import PlatformWalletCredentials
    return PlatformWalletCredentials.objects.filter(pk=1).first()


def _apple_from_row(row, source):
    if row is None or not row.apple_complete:
        return None
    from django.utils import timezone
    if row.apple_cert_expires_at is not None and row.apple_cert_expires_at <= timezone.now():
        return None  # an expired certificate cannot sign: fall through to the next source
    try:
        return AppleCredentials(row.apple_pass_type_id, row.apple_team_id, row.secret("apple_cert_pem").encode(),
                                row.secret("apple_key_pem").encode(), row.secret("apple_wwdr_pem").encode(), source)
    except Exception:  # noqa: BLE001 - an undecryptable row (rotated key) reads as "not configured", never a 500
        return None


def _google_from_row(row, source):
    if row is None or not row.google_complete:
        return None
    try:
        raw = row.secret("google_service_account")
    except Exception:  # noqa: BLE001 - see _apple_from_row
        return None
    return _google(row.google_issuer_id, row.google_class_prefix or "spaceworks_card", raw, source)


def _google(issuer_id, prefix, raw_account, source):
    try:
        data = json.loads(raw_account)
        return GoogleCredentials(issuer_id, prefix, data["client_email"], data["private_key"], source)
    except (ValueError, KeyError, TypeError):
        return None


def _apple_from_files():
    if not (getattr(settings, "WALLET_APPLE_PASS_TYPE_ID", "") and getattr(settings, "WALLET_APPLE_TEAM_ID", "")
            and _file("WALLET_APPLE_CERT_FILE") and _file("WALLET_APPLE_KEY_FILE") and _file("WALLET_APPLE_WWDR_FILE")):
        return None
    return AppleCredentials(settings.WALLET_APPLE_PASS_TYPE_ID, settings.WALLET_APPLE_TEAM_ID,
                            _file("WALLET_APPLE_CERT_FILE").read_bytes(), _file("WALLET_APPLE_KEY_FILE").read_bytes(),
                            _file("WALLET_APPLE_WWDR_FILE").read_bytes(), "deployment")


def _google_from_file():
    if not (getattr(settings, "WALLET_GOOGLE_ISSUER_ID", "") and _file("WALLET_GOOGLE_SERVICE_ACCOUNT_FILE")):
        return None
    return _google(settings.WALLET_GOOGLE_ISSUER_ID, "spaceworks_card",
                   _file("WALLET_GOOGLE_SERVICE_ACCOUNT_FILE").read_text(), "deployment")


def _platform_fallback(makerspace):
    """The superadmin's saved credentials, for the platform itself and for every space (decision 240)."""
    return _platform_row()


def _fallback_allowed(makerspace):
    """Decision 281: a Space Manager may switch the platform certificates off for their space."""
    if makerspace is None:
        return True
    from apps.managed_hosting.platform_switch import platform_allowed
    return platform_allowed(makerspace, "wallet")


def apple_for(makerspace=None):
    """The Apple credentials to sign this space's passes with, or None (feature off)."""
    own = _apple_from_row(_space_row(makerspace), "space")
    if own or not _fallback_allowed(makerspace):
        return own
    return _apple_from_row(_platform_fallback(makerspace), "platform") or _apple_from_files()


def google_for(makerspace=None):
    own = _google_from_row(_space_row(makerspace), "space")
    if own or not _fallback_allowed(makerspace):
        return own
    return _google_from_row(_platform_fallback(makerspace), "platform") or _google_from_file()


def configured_platforms(makerspace=None):
    """("apple", "google") entries that can sign for this space; platform-level when no space is given."""
    return tuple(name for name, creds in (("apple", apple_for(makerspace)), ("google", google_for(makerspace)))
                 if creds is not None)


def auth_token(serial, generation=1):
    """The pass authentication token: derived, never stored (only its digest is)."""
    key = hashlib.sha256(("card-wallet-pass:" + settings.SECRET_KEY).encode()).digest()
    return hmac.new(key, f"{serial}:{generation}".encode(), hashlib.sha256).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
