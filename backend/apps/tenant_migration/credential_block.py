"""Sign-in credentials travel with a space's people (#128 C-18, #137 Q-B1).

A PORTABLE tenant archive carries one credential block per person in its user closure
(staff and members alike): the password hash, the authenticator secret with its recovery
code digests, and passkeys. Each entry is AES-GCM ciphertext under the space's active DEK,
bound to (source makerspace, ``CREDENTIAL_TABLE``, source user id, ``CREDENTIAL_FIELD``),
so no credential is ever plaintext in the archive. Sessions, device grants, refresh
families, remembered devices and pending challenges never travel.

On import a CREATED person gets their credentials (and so can sign in on the target); a
LINKED person keeps the target's own credentials and the block entry is ignored. A passkey
is installed only when its relying-party ID is a host of the target (passkeys are bound to
a domain). A source without encryption (no DEK) carries no block: its people reset.
"""

import json

from django.conf import settings

BLOCK_PATH = "global/credentials.json"
CREDENTIAL_TABLE = "accounts_user_credentials"
CREDENTIAL_FIELD = "credential_block"
PERSON_KIND = "member"


def write_credential_block(root, makerspace, keys):
    """Write the block for every person in ``root``'s users.csv; return the entry count."""
    import csv

    from apps.accounts.models import User
    from apps.encryption.crypto import encrypt

    active = [key for key in keys if key.get("status") == "active" and "dek" in key]
    path = root / "global" / "users.csv"
    if not active or not path.is_file():
        return 0
    key = active[-1]
    with path.open(encoding="utf-8", newline="") as handle:
        ids = [row["id"] for row in csv.DictReader(handle) if row.get("account_kind") == PERSON_KIND]
    entries = []
    for user in User._base_manager.filter(pk__in=ids).order_by("pk"):
        payload = credentials_of(user)
        if payload is None:
            continue
        entries.append({"source_user_id": str(user.pk), "envelope": encrypt(
            json.dumps(payload, sort_keys=True).encode("utf-8"), key["dek"], key_version=int(key["version"]),
            makerspace_id=makerspace.pk, table=CREDENTIAL_TABLE, pk=user.pk, field=CREDENTIAL_FIELD)})
    if entries:
        (root / BLOCK_PATH).write_text(json.dumps({"version": 1, "entries": entries}, sort_keys=True),
                                       encoding="utf-8")
    return len(entries)


def credentials_of(user):
    """The portable credentials of one live person, or None when there are none."""
    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.makerspaces.secrets import decrypt_value

    if (not user.is_active or user.deletion_requested_at is not None or user.account_purged_at is not None
            or user.is_walk_in or user.is_tenant_dump_stub):
        return None
    payload = {}
    if user.has_usable_password():
        payload["password"] = user.password
    mfa = UserMFA.objects.filter(user=user, enabled_at__isnull=False).exclude(secret="").first()
    if mfa is not None:
        payload["totp"] = {"secret": decrypt_value(mfa.secret), "enabled_at": mfa.enabled_at.isoformat(),
                           "recovery_digests": list(mfa.recovery_digests)}
    passkeys = [{
        "credential_id": item.credential_id, "public_key": bytes(item.public_key).hex(),
        "sign_count": item.sign_count, "transports": item.transports, "aaguid": item.aaguid,
        "backed_up": item.backed_up, "rp_id": item.rp_id, "name": item.name,
    } for item in WebAuthnCredential.objects.filter(user=user).order_by("pk")]
    if passkeys:
        payload["passkeys"] = passkeys
    return payload or None


def read_credential_block(archive, source_makerspace_id, deks):
    """``{source_user_id: payload}`` decrypted with the carried DEKs (empty without a block)."""
    from apps.encryption.crypto import decrypt_with_key_loader

    from .insertion_errors import ArchiveFormatError

    if not (archive.root / BLOCK_PATH).is_file():
        return {}
    block = archive.json(BLOCK_PATH)
    if block.get("version") != 1 or not isinstance(block.get("entries"), list):
        raise ArchiveFormatError("The credential block has an unsupported shape.")
    result = {}
    for entry in block["entries"]:
        source_id = str(entry["source_user_id"])
        plaintext = decrypt_with_key_loader(
            entry["envelope"], makerspace_id=int(source_makerspace_id), table=CREDENTIAL_TABLE,
            pk=int(source_id), field=CREDENTIAL_FIELD, load_dek=lambda version: deks[version])
        result[source_id] = json.loads(plaintext)
    return result


def install_credentials(user, payload, *, target):
    """Install a CREATED person's travelled credentials; return the passkeys installed."""
    from django.utils.dateparse import parse_datetime

    from apps.accounts.models_mfa import UserMFA
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.makerspaces.secrets import encrypt_value

    if payload.get("password"):
        user.password = payload["password"]
        user.save(update_fields=["password"])
    totp = payload.get("totp")
    if totp:
        UserMFA.objects.update_or_create(user=user, defaults={
            "secret": encrypt_value(totp["secret"]), "enabled_at": parse_datetime(totp["enabled_at"]),
            "recovery_digests": list(totp.get("recovery_digests") or [])})
    hosts = target_hosts(target)
    installed = 0
    for item in payload.get("passkeys") or ():
        if item.get("rp_id") not in hosts or WebAuthnCredential.objects.filter(
                credential_id=item["credential_id"]).exists():
            continue
        WebAuthnCredential.objects.create(
            user=user, credential_id=item["credential_id"], public_key=bytes.fromhex(item["public_key"]),
            sign_count=item.get("sign_count") or 0, transports=item.get("transports") or [],
            aaguid=item.get("aaguid") or "", backed_up=bool(item.get("backed_up")), rp_id=item["rp_id"],
            name=(item.get("name") or "")[:64])
        installed += 1
    return installed


def target_hosts(target):
    """The relying-party IDs a passkey may keep on this deployment for ``target``."""
    from urllib.parse import urlparse

    hosts = {urlparse(settings.PUBLIC_APP_BASE_URL).hostname} if settings.PUBLIC_APP_BASE_URL else set()
    if target.frontend_domain and target.frontend_domain_status == type(target).DomainStatus.VERIFIED:
        hosts.add(target.frontend_domain)
    return {host for host in hosts if host}
