"""Global member signup and email-verification challenge lifecycle."""

from django.utils.translation import gettext_lazy
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts import audit_events
from apps.accounts.models import EmailVerificationChallenge, User
from apps.accounts.staff_identity import PERSON_KIND, is_person, person_q
from apps.integrations.email import send_email_verification_otp
from apps.makerspaces.limits import reserve_platform_otp_quota

logger = logging.getLogger(__name__)
RESEND_COOLDOWN = timedelta(seconds=60)
CHALLENGE_TTL = timedelta(minutes=10)
SELF_REGISTRATION_HOLD_TTL = timedelta(hours=24)
GENERIC_CONFIRM_ERROR = gettext_lazy("Invalid or expired verification code.")


class ChallengeCooldown(Exception):
    pass


def _normalize_email(email):
    return email.strip().lower()


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _digest(code):
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_challenge(user, requested_handle=None):
    """Persist a fresh challenge and attempt delivery without exposing delivery state.

    `requested_handle` is the username a NEW sign-up chose (M14); a resend carries the last one over.
    """
    now = timezone.now()
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        # A walk-in's address is staff-typed contact data, not identity proof, and only a
        # person verifies (a converted staff address included, #65). Returning quietly
        # preserves the endpoint's account-enumeration-safe acknowledgement.
        if not is_person(locked_user) or locked_user.is_walk_in:
            return None
        email = _normalize_email(locked_user.email)
        if EmailVerificationChallenge.objects.filter(
            user=locked_user, email=email, last_sent_at__gte=now - RESEND_COOLDOWN
        ).exists():
            raise ChallengeCooldown
        EmailVerificationChallenge.objects.filter(
            user=locked_user,
            email=email,
            consumed_at__isnull=True,
            failed_attempts__lt=5,
            expires_at__gt=now,
        ).update(consumed_at=now)
        if requested_handle is None:
            requested_handle = (EmailVerificationChallenge.objects.filter(user=locked_user)
                                .order_by("-created_at", "-pk").values_list("requested_handle", flat=True)
                                .first() or "")
        code = _generate_otp()
        challenge = EmailVerificationChallenge.objects.create(
            user=locked_user,
            email=email,
            code_digest=_digest(code),
            expires_at=now + CHALLENGE_TTL,
            last_sent_at=now,
            requested_handle=requested_handle,
        )
        quota_reserved = reserve_platform_otp_quota()
    sent = False
    if quota_reserved:
        try:
            sent = bool(send_email_verification_otp(email, code))
        except Exception:
            logger.exception("email_verification_dispatch_failed")
    audit_events.record_auth_event(
        locked_user,
        "member.email_verification_requested",
        target=locked_user,
        meta={"email_hash": audit_events.fingerprint(email), "email_sent": sent},
    )
    return challenge


def _record_confirm_failure(user, challenge=None):
    meta = {}
    if challenge is not None:
        challenge.failed_attempts += 1
        challenge.save(update_fields=["failed_attempts"])
        meta["email_hash"] = audit_events.fingerprint(challenge.email)
    audit_events.record_auth_event(
        user, "member.email_verification_failed", target=user, meta=meta
    )


def confirm_challenge(user, code):
    now = timezone.now()
    failed = False
    refused_walk_in = False
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not is_person(locked_user):
            raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
        email = _normalize_email(locked_user.email)
        # Resolve ONLY the caller's own newest usable challenge for their current email.
        # A foreign user has no matching row, so guessing IDs cannot burn a victim's attempts.
        challenge = (
            EmailVerificationChallenge.objects.select_for_update()
            .filter(
                user=locked_user,
                email=email,
                consumed_at__isnull=True,
                failed_attempts__lt=5,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None or not hmac.compare_digest(
            challenge.code_digest, _digest(code)
        ):
            _record_confirm_failure(locked_user, challenge)
            failed = True
        else:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            if locked_user.is_walk_in:
                refused_walk_in = True
                audit_events.record_auth_event(
                    locked_user,
                    "member.email_verification_refused_walk_in",
                    target=locked_user,
                    meta={"email_hash": audit_events.fingerprint(challenge.email)},
                )
            else:
                User.objects.filter(
                    pk=locked_user.pk, email_verified_at__isnull=True
                ).update(email_verified_at=now)
                EmailVerificationChallenge.objects.filter(
                    user=locked_user,
                    email=challenge.email,
                    consumed_at__isnull=True,
                ).update(consumed_at=now)
                user.email_verified_at = now
                if locked_user.self_registered_at is not None:
                    # M14: the sign-up's username is claimed only now that the address is proven.
                    from apps.makerspaces.public_profile_handles import claim_requested_handle
                    claim_requested_handle(locked_user, challenge.requested_handle)
                audit_events.record_auth_event(
                    locked_user,
                    "member.email_verified",
                    target=locked_user,
                    meta={"email_hash": audit_events.fingerprint(challenge.email)},
                )
    # The refusal consumed a valid challenge and wrote an audit row. Raising inside the
    # atomic block would roll both state changes back and silently reopen the attempt.
    if failed or refused_walk_in:
        raise serializers.ValidationError({"detail": GENERIC_CONFIRM_ERROR})
    from apps.makerspaces.import_adoption import adopt_pending_memberships_for_user

    adopt_pending_memberships_for_user(user)
    return challenge


def register_member(display_name, email, phone, password, handle=""):
    """Create a global member or quietly resend verification for an existing one."""
    email = _normalize_email(email)
    # Validate the password BEFORE the existence lookup so a weak password always
    # returns the same 400 whether or not the email is already registered — otherwise
    # "weak password" would 400 for new emails but generic-ack for existing ones,
    # leaking account existence (enumeration oracle).
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        from apps.accounts.password_breach import error_body
        raise serializers.ValidationError(error_body("password", exc)) from exc
    # The chosen username's GRAMMAR is checked here, before the lookup, for the same reason; whether
    # it is free is decided only when the email is confirmed (M14), so this request never claims it.
    from apps.makerspaces.public_profile_handles import normalize_handle
    handle = normalize_handle(handle) if handle else ""
    created = False
    now = timezone.now()
    with transaction.atomic():
        user = (
            User.objects.select_for_update().filter(person_q(), email__iexact=email).first()
        )
        if _self_registration_is_releasable(user, now):
            _release_self_registration(user, now)
            user = None
        if user is None:
            try:
                # The savepoint keeps a concurrent unique-email race from poisoning
                # the outer transaction before we can resolve the winning row.
                with transaction.atomic():
                    user = User(
                        username=f"member_{uuid.uuid4().hex}",
                        account_kind=PERSON_KIND,
                        display_name=display_name,
                        email=email,
                        phone=phone,
                        role=User.Role.REQUESTER,
                        is_active=True,
                        self_registered_at=now,
                    )
                    user.set_password(password)
                    user.save()
                    created = True
                    # Decision 308 asks for the username at sign-up; SECURITY-REVIEW M14 moves the CLAIM
                    # to email confirmation. Claiming it here would let anyone learn whether an address
                    # is registered: "taken" afterwards only for a brand-new account.
            except IntegrityError:
                user = (
                    User.objects.select_for_update()
                    .filter(person_q(), email__iexact=email)
                    .first()
                )

    # A walk-in is a person record, not an enrollable account. Silence is required
    # here by the endpoint's account-enumeration contract.
    if user is not None and user.is_walk_in:
        return None

    audit_events.record_auth_event(
        user,
        "member.signup_requested",
        target=user,
        meta={"email_hash": audit_events.fingerprint(email)},
    )
    if user and user.is_active and user.email_verified_at is None:
        try:
            issue_challenge(user, handle if created else None)
        except ChallengeCooldown:
            pass
    return user


from .services_registration_release import (  # noqa: E402 - re-export after the shared helpers
    _release_self_registration, _self_registration_is_releasable,
)
