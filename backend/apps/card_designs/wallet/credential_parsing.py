"""Validate wallet-pass signing material before it is stored (decision 223(l)).

Pure functions: key material in, normalised PEM plus public facts out. Errors are
`ValidationError`s keyed by API field name and NEVER echo a value. Apple material may arrive
as a .p12 (base64) or as PEM files; it is stored as unencrypted PEM (encrypted at rest by the
model). The Pass Type ID and Team ID must match the certificate subject (UID and OU) so a
mismatched upload fails here rather than as a silent "invalid pass" on a phone.
"""
import base64
import binascii
import hashlib
import json
import re

from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

ISSUER = re.compile(r"^\d{1,20}$")
PREFIX = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_BYTES = 64 * 1024
EXPIRY_WARNING_DAYS = 30


def _fail(field, message):
    raise ValidationError({field: [message]})


def _serialization():
    from cryptography.hazmat.primitives import serialization
    return serialization


def _public_der(public_key):
    ser = _serialization()
    return public_key.public_bytes(ser.Encoding.DER, ser.PublicFormat.SubjectPublicKeyInfo)


def _key_pem(key):
    ser = _serialization()
    return key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()).decode()


def _cert_pem(cert):
    return cert.public_bytes(_serialization().Encoding.PEM).decode()


def _text(value, field, limit=MAX_BYTES):
    value = (value or "").strip()
    if len(value.encode()) > limit:
        _fail(field, gettext("This file is too large."))
    return value


def _load_cert(pem, field):
    from cryptography import x509
    try:
        return x509.load_pem_x509_certificate(pem.encode())
    except ValueError:
        _fail(field, gettext("This is not a PEM certificate."))


def _load_key(pem, passphrase, field):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    try:
        return load_pem_private_key(pem.encode(), password=passphrase.encode() if passphrase else None)
    except (ValueError, TypeError):
        _fail(field, gettext("The private key could not be read; check the file and passphrase."))


def _from_p12(raw, password):
    from cryptography.hazmat.primitives.serialization import pkcs12
    try:
        data = base64.b64decode(raw, validate=False)
        if len(data) > MAX_BYTES:
            _fail("apple_p12", gettext("This file is too large."))
        key, cert, extra = pkcs12.load_key_and_certificates(data, password.encode() if password else None)
    except (ValueError, binascii.Error, TypeError):
        _fail("apple_p12", gettext("The .p12 file could not be opened; check the file and password."))
    if key is None or cert is None:
        _fail("apple_p12", gettext("The .p12 file must hold the certificate and its private key."))
    return _cert_pem(cert), _key_pem(key), (_cert_pem(extra[0]) if extra else "")


def _subject(cert, oid):
    values = cert.subject.get_attributes_for_oid(oid)
    return values[0].value if values else ""


def parse_apple(data, stored):
    """Merge the submitted Apple fields over the stored secrets and validate the whole set.

    `stored` maps cert/key/wwdr to the current plaintext PEMs (empty when none): changing only
    the Pass Type ID or Team ID keeps the saved certificate. Returns the values to store.
    """
    from cryptography.x509.oid import NameOID
    cert_pem, key_pem, wwdr_pem = stored.get("cert", ""), stored.get("key", ""), stored.get("wwdr", "")
    if data.get("apple_p12"):
        cert_pem, key_pem, p12_wwdr = _from_p12(data["apple_p12"], data.get("apple_p12_password", ""))
        wwdr_pem = p12_wwdr or wwdr_pem
    if data.get("apple_cert_pem"):
        cert_pem = _text(data["apple_cert_pem"], "apple_cert_pem")
    if data.get("apple_key_pem"):
        key_pem = _text(data["apple_key_pem"], "apple_key_pem")
        key_pem = _key_pem(_load_key(key_pem, data.get("apple_key_passphrase", ""), "apple_key_pem"))
    if data.get("apple_wwdr_pem"):
        wwdr_pem = _text(data["apple_wwdr_pem"], "apple_wwdr_pem")
    pass_type_id = (data.get("apple_pass_type_id") or stored.get("pass_type_id", "")).strip()
    team_id = (data.get("apple_team_id") or stored.get("team_id", "")).strip()
    for field, value in (("apple_pass_type_id", pass_type_id), ("apple_team_id", team_id), ("apple_cert_pem", cert_pem),
                         ("apple_key_pem", key_pem), ("apple_wwdr_pem", wwdr_pem)):
        if not value:
            _fail(field, gettext("This is required to set up Apple Wallet."))
    cert, wwdr = _load_cert(cert_pem, "apple_cert_pem"), _load_cert(wwdr_pem, "apple_wwdr_pem")
    key = _load_key(key_pem, "", "apple_key_pem")
    if _public_der(cert.public_key()) != _public_der(key.public_key()):
        _fail("apple_key_pem", gettext("The private key does not belong to this certificate."))
    expires = cert.not_valid_after_utc
    if expires <= timezone.now():
        _fail("apple_cert_pem", gettext("This certificate has expired."))
    if (uid := _subject(cert, NameOID.USER_ID)) and uid != pass_type_id:
        _fail("apple_pass_type_id", gettext("The Pass Type ID does not match the certificate."))
    if (unit := _subject(cert, NameOID.ORGANIZATIONAL_UNIT_NAME)) and unit != team_id:
        _fail("apple_team_id", gettext("The Team ID does not match the certificate."))
    return {"pass_type_id": pass_type_id, "team_id": team_id, "cert": _cert_pem(cert), "key": _key_pem(key),
            "wwdr": _cert_pem(wwdr), "fingerprint": cert.fingerprint(_hash()).hex(), "expires_at": expires}


def _hash():
    from cryptography.hazmat.primitives import hashes
    return hashes.SHA256()


def parse_google(data, stored):
    """Validate the Google fields (issuer id, class prefix, service-account JSON) and return the values to store."""
    issuer = (data.get("google_issuer_id") or stored.get("issuer_id", "")).strip()
    prefix = (data.get("google_class_prefix") or stored.get("class_prefix", "") or "spaceworks_card").strip()
    raw = _text(data.get("google_service_account"), "google_service_account") or stored.get("service_account", "")
    if not ISSUER.match(issuer):
        _fail("google_issuer_id", gettext("The issuer id is the number shown in the Google Wallet console."))
    if not PREFIX.match(prefix):
        _fail("google_class_prefix", gettext("Use letters, numbers, underscore or hyphen (up to 40)."))
    if not raw:
        _fail("google_service_account", gettext("This is required to set up Google Wallet."))
    try:
        account = json.loads(raw)
        client_email, private_key = account["client_email"], account["private_key"]
        key = _load_key(private_key, "", "google_service_account")
        if account.get("type", "service_account") != "service_account" or "@" not in client_email:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        _fail("google_service_account", gettext("This is not a Google service-account key file."))
    minimal = json.dumps({"type": "service_account", "client_email": client_email, "private_key": private_key})
    return {"issuer_id": issuer, "class_prefix": prefix, "service_account": minimal,
            "fingerprint": hashlib.sha256(_public_der(key.public_key())).hexdigest()}
