"""Platform wallet-pass credentials (Q-I11): configured once by the operator, never per space.

Apple: a Pass Type ID certificate + key and Apple's WWDR intermediate (PEM files).
Google: an issuer id and a service-account JSON key file. The buttons stay hidden
until a platform is configured; every value is read from settings, never stored.
"""
import hashlib
import hmac
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


def _file(name):
    value = getattr(settings, name, "") or ""
    return Path(value) if value and Path(value).is_file() else None


def apple_ready():
    return bool(getattr(settings, "WALLET_APPLE_PASS_TYPE_ID", "") and getattr(settings, "WALLET_APPLE_TEAM_ID", "")
                and _file("WALLET_APPLE_CERT_FILE") and _file("WALLET_APPLE_KEY_FILE")
                and _file("WALLET_APPLE_WWDR_FILE"))


def google_ready():
    return bool(getattr(settings, "WALLET_GOOGLE_ISSUER_ID", "") and _file("WALLET_GOOGLE_SERVICE_ACCOUNT_FILE"))


def configured_platforms():
    return tuple(name for name, ready in (("apple", apple_ready()), ("google", google_ready())) if ready)


@lru_cache(maxsize=1)
def apple_material():
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    # The key file is an unencrypted PEM mounted as a secret file (never an env value).
    cert = x509.load_pem_x509_certificate(_file("WALLET_APPLE_CERT_FILE").read_bytes())
    key = load_pem_private_key(_file("WALLET_APPLE_KEY_FILE").read_bytes(), password=None)
    wwdr = x509.load_pem_x509_certificate(_file("WALLET_APPLE_WWDR_FILE").read_bytes())
    return cert, key, wwdr


@lru_cache(maxsize=1)
def google_account():
    data = json.loads(_file("WALLET_GOOGLE_SERVICE_ACCOUNT_FILE").read_text())
    return {"client_email": data["client_email"], "private_key": data["private_key"]}


def auth_token(serial, generation=1):
    """The pass authentication token: derived, never stored (only its digest is)."""
    key = hashlib.sha256(("card-wallet-pass:" + settings.SECRET_KEY).encode()).digest()
    return hmac.new(key, f"{serial}:{generation}".encode(), hashlib.sha256).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
