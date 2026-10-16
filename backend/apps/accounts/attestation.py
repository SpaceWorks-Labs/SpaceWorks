import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models_devices import (
    DeviceAttestationChallenge,
    NativeAppRegistration,
)


class AttestationUnavailable(Exception):
    pass


class AttestationRejected(Exception):
    pass


@dataclass(frozen=True)
class VerifiedAttestation:
    subject: str
    metadata: dict = field(default_factory=dict)


def readiness_mode(platform, signing_identity=None):
    """Select one verifier; a configured verifier's failure never enables a bypass."""
    if platform not in {"apple", "android"}:
        return "unavailable"
    prefix = f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY"
    url = getattr(settings, f"{prefix}_URL", "")
    token = getattr(settings, f"{prefix}_TOKEN", "")
    if url and token:
        return "external"
    # App Attest uses public trust material; the per-app team ID is checked by
    # configured_app, and no deployment-private Apple credential is required.
    if platform == "apple" and isinstance(signing_identity, str) and re.fullmatch(r"[A-Z0-9]{10}", signing_identity):
        return "in_process"
    if platform == "android":
        from apps.accounts.models_attestation import PlatformAttestationSettings
        row = PlatformAttestationSettings.objects.filter(pk=1).first()
        if row and row.play_integrity_service_account:
            return "in_process"
    if settings.DEVICE_ATTESTATION_DEV_INSECURE:
        return "development_insecure"
    return "unavailable"


def challenge_digest(raw):
    return hmac.new(settings.SECRET_KEY.encode(), str(raw).encode(), hashlib.sha256).hexdigest()


def configured_app(platform, verifier_config_key, environment):
    entry = (
        getattr(settings, "DEVICE_ATTESTATION_APPS", {})
        .get(platform, {})
        .get(verifier_config_key)
    )
    if not isinstance(entry, dict):
        raise AttestationUnavailable("Device attestation is unavailable.")
    signing_identity = str(entry.get("signing_identity") or "")
    if not signing_identity or environment not in (entry.get("environments") or []):
        raise AttestationUnavailable("Device attestation is unavailable.")
    mode = readiness_mode(platform, signing_identity)
    if mode == "external":
        url = getattr(settings, f"DEVICE_{platform.upper()}_ATTESTATION_VERIFY_URL")
        parsed = urlsplit(str(url))
        if parsed.scheme != "https" or not parsed.netloc:
            raise AttestationUnavailable("Device attestation is unavailable.")
    if mode == "unavailable":
        raise AttestationUnavailable('Device attestation is unavailable.')
    return signing_identity


def _approved_registration(*, platform, app_id, environment):
    """Resolve the DEPLOYMENT-GLOBAL approved registration for an app identity.

    Tenant-scoped registrations are deliberately NOT resolvable here. The challenge route
    is unauthenticated, so it carries no trustworthy makerspace context, and picking a
    tenant registration because it happens to be the only one would (a) hand one tenant's
    approved app to any user, and (b) let the resulting grant later select a DIFFERENT
    makerspace where that user has membership, bypassing that tenant's approval boundary.
    Falling back on row count is resolving authority by coincidence.

    Tenant-scoped registrations therefore remain inert until the phase that carries a
    verified makerspace context into this path. The column and its uniqueness rules exist
    now so that phase does not need a second migration.
    """
    registration = NativeAppRegistration.objects.filter(
        makerspace__isnull=True,
        platform=platform,
        app_id=app_id,
        environment=environment,
        status=NativeAppRegistration.Status.APPROVED,
    ).first()
    if registration is None:
        raise AttestationUnavailable('Device attestation is unavailable.')
    return registration


def create_challenge(*, platform, app_id, environment):
    registration = _approved_registration(
        platform=platform,
        app_id=app_id,
        environment=environment,
    )
    signing_identity = configured_app(
        platform,
        registration.verifier_config_key,
        environment,
    )
    ttl = settings.DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS
    if ttl <= 0:
        raise AttestationUnavailable('Device attestation is unavailable.')
    raw = secrets.token_urlsafe(48)
    DeviceAttestationChallenge.objects.create(
        registration=registration,
        platform=platform, app_id=app_id, signing_identity=signing_identity,
        environment=environment, challenge_digest=challenge_digest(raw),
        expires_at=timezone.now() + timedelta(
            seconds=ttl
        ),
    )
    return raw


def live_approved_challenge(raw_challenge):
    """Return an unspent challenge whose app registration remains approved."""
    now = timezone.now()
    challenge = (
        DeviceAttestationChallenge.objects.select_related("registration")
        .filter(
            challenge_digest=challenge_digest(raw_challenge),
            consumed_at__isnull=True,
            expires_at__gt=now,
            registration__status=NativeAppRegistration.Status.APPROVED,
        )
        .first()
    )
    return challenge if challenge and _authority_matches(challenge) else None


def consume_attestation_challenge(
    raw_challenge, *, expected_id=None, platform=None, app_id=None, environment=None
):
    """Burn and validate a challenge, optionally against a nonce-bound row."""
    now = timezone.now()
    with transaction.atomic():
        rows = DeviceAttestationChallenge.objects.select_for_update().select_related(
            "registration"
        )
        if expected_id is None:
            challenge = rows.filter(
                challenge_digest=challenge_digest(raw_challenge)
            ).first()
        else:
            challenge = rows.filter(pk=expected_id).first()
        if challenge is None or challenge.consumed_at is not None:
            return None
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])

    expected = (platform, app_id, environment)
    actual = (challenge.platform, challenge.app_id, challenge.environment)
    supplied_identity_matches = all(
        wanted is None or wanted == observed
        for wanted, observed in zip(expected, actual)
    )
    return challenge if (
        challenge.expires_at > now
        and hmac.compare_digest(
            challenge.challenge_digest, challenge_digest(raw_challenge)
        )
        and supplied_identity_matches
        and challenge.registration.status == NativeAppRegistration.Status.APPROVED
        and _authority_matches(challenge)
    ) else None


def _authority_matches(challenge):
    registration = challenge.registration
    return not (
        challenge.platform != registration.platform
        or challenge.app_id != registration.app_id
        or challenge.environment != registration.environment
    )


def verify_attestation(challenge, raw_challenge, payload):
    # Simulators/emulators cannot attest, and Apple's in-process mode is selected by the
    # team ID alone, so the explicit development payload is honoured before mode dispatch
    # -- still only with DEBUG on (checks.E001 refuses the flag otherwise) and only for a
    # development registration.
    if (settings.DEVICE_ATTESTATION_DEV_INSECURE and settings.DEBUG
            and challenge.environment == "development" and payload == {"type": "development"}):
        return VerifiedAttestation(subject="development")
    mode = readiness_mode(challenge.platform, challenge.signing_identity)
    if mode == "unavailable":
        raise AttestationUnavailable("Device attestation is unavailable.")
    if mode == "development_insecure":
        if not settings.DEBUG or challenge.environment != "development" or payload != {"type": "development"}:
            raise AttestationRejected("Attestation was rejected.")
        return VerifiedAttestation(subject="development")
    if mode == "in_process":
        if challenge.platform == "apple":
            from apps.accounts.attestation_app_attest import verify_app_attest
            return verify_app_attest(challenge, raw_challenge, payload)
        from apps.accounts.attestation_play_integrity import verify_play_integrity
        return verify_play_integrity(challenge, raw_challenge, payload)
    if challenge.platform == "apple":
        from apps.accounts.attestation_apple import verify_apple_attestation
        subject = verify_apple_attestation(challenge, raw_challenge, payload)
    elif challenge.platform == "android":
        from apps.accounts.attestation_android import verify_android_attestation
        subject = verify_android_attestation(challenge, raw_challenge, payload)
    else:
        raise AttestationRejected("Attestation was rejected.")
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise AttestationRejected("Attestation was rejected.")
    return VerifiedAttestation(subject=subject)
