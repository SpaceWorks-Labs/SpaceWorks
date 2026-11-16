"""Releasing a stale, never-verified self-registration so its email can be used again.

Split from `services_registration` (file ceiling); that module re-exports both helpers.
"""

from apps.accounts import audit_events
from apps.accounts.models import EmailVerificationChallenge

from .services_registration import SELF_REGISTRATION_HOLD_TTL, _normalize_email


def _self_registration_is_releasable(user, now):
    """Whether a stale unverified signup may be discarded so its email is reusable.

    An unproven email is not on its own proof that the record is abandoned. Releasing
    DEACTIVATES the account, so it must be refused whenever the row carries any other
    credential or authority -- a linked social identity, a verified phone number, or a
    makerspace membership somebody granted. Post-P3-ii an unverified session is
    verification-only and cannot reach the link endpoints, but migration 0022 stamps
    `self_registered_at` onto pre-existing rows, and those predate that restriction. This
    is the walk-in lesson in reverse: enumerate every signal that the record is a real
    account BEFORE discarding it, rather than closing each path as someone points at it.
    """
    if not (
        user
        and user.self_registered_at is not None
        and user.email_verified_at is None
        and user.self_registered_at <= now - SELF_REGISTRATION_HOLD_TTL
    ):
        return False
    from apps.accounts.models_social import SocialIdentity
    from apps.makerspaces.models import MakerspaceMembership

    if user.phone_e164 and user.phone_verified_at is not None:
        return False
    if SocialIdentity.objects.filter(user=user).exists():
        return False
    if (MakerspaceMembership.objects.filter(user=user).exists()
            or MakerspaceMembership.staff_tracks.filter(user=user).exists()):
        return False
    return True


def _release_self_registration(user, now):
    """Deactivate a stale unverified signup so its unproven email can be reused."""
    email = _normalize_email(user.email)
    EmailVerificationChallenge.objects.filter(
        user=user, consumed_at__isnull=True
    ).update(consumed_at=now)
    user.email = ""
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=["email", "is_active", "password"])
    # L-P1: an abandoned sign-up must not keep a username squatted (older sign-ups claimed at once).
    from apps.makerspaces.models_profiles import PublicHandle
    PublicHandle.objects.filter(user=user).delete()
    audit_events.record_auth_event(
        user,
        "member.signup_expired",
        target=user,
        meta={"email_hash": audit_events.fingerprint(email)},
    )
