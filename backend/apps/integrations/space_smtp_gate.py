"""A space's own SMTP account is used only after a test message from it was accepted (parity E-B8, A19).

The fingerprint hashes every setting that decides where mail goes and as whom (host, port, login, the stored
ciphertext of the password, TLS mode, From). Changing any of them changes the hash, so the proof expires by
itself; there is no flag to forget to clear. API providers (Resend, Postmark, ...) are outside this gate.
"""

import hashlib

PROVIDERS_WITH_OWN_SMTP = ("", "smtp")


def own_smtp_in_use(makerspace) -> bool:
    """True when the space's configured own transport is SMTP (explicit, or the legacy host-only form)."""
    provider = (getattr(makerspace, "email_provider", "") or "").strip()
    host = (getattr(makerspace, "smtp_host", "") or "").strip()
    return bool(host) and provider in PROVIDERS_WITH_OWN_SMTP


def smtp_fingerprint(makerspace) -> str:
    parts = (
        (makerspace.smtp_host or "").strip().lower(), str(makerspace.smtp_port), makerspace.smtp_username or "",
        makerspace.smtp_password or "", str(bool(makerspace.smtp_use_ssl)), str(bool(makerspace.smtp_use_tls)),
        (makerspace.smtp_from_email or "").strip().lower(),
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def smtp_verified(makerspace) -> bool:
    stored = getattr(makerspace, "smtp_verified_fingerprint", "") or ""
    return bool(stored) and stored == smtp_fingerprint(makerspace)


def own_smtp_active(makerspace) -> bool:
    """False when the space has no own SMTP, or has one that has not passed its test yet."""
    return own_smtp_in_use(makerspace) and smtp_verified(makerspace)


def mark_verified(makerspace, now) -> None:
    makerspace.smtp_verified_fingerprint = smtp_fingerprint(makerspace)
    makerspace.smtp_verified_at = now
    makerspace.save(update_fields=["smtp_verified_fingerprint", "smtp_verified_at", "updated_at"])
