"""Creation-only device authority policy; existing grants retain refresh access."""

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.native_app_identity import eligible_registration_q, matched_signing_identity
from apps.accounts import audit_events
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, NativeAppRegistration
from apps.accounts.services_device_tokens import (
    assert_mobile_grant_creation_enabled, issue_device_token_pair,
)
from apps.accounts.services_staff_authority import has_local_staff_authority
from apps.accounts.session_issuance import lock_session_user


logger = logging.getLogger(__name__)


class DeviceSuperadminNotSupported(PermissionDenied):
    default_code = "device_superadmin_not_supported"

    def __init__(self, user):
        self.user = user
        super().__init__({
            "detail": "Superadmin accounts cannot create device grants.",
            "code": self.default_code,
        })


def assert_grant_user_allowed(user):
    if user.is_superuser or user.role == User.Role.SUPERADMIN:
        raise DeviceSuperadminNotSupported(user)


def audit_grant_refusal(exc):
    """Call outside the grant/MFA transaction so rollback cannot erase the refusal."""
    audit_events.record_auth_event(
        exc.user, "auth.device_login_failed", target=exc.user,
        meta={"reason": exc.default_code},
    )
    logger.warning("Device grant creation refused", extra={
        "user_id": exc.user.pk, "reason": exc.default_code,
    })


def authority_for_login(user, *, login_method):
    # Provenance comes from the issuer or server-owned MFA context, never request data.
    if login_method in {"password", "social"} and has_local_staff_authority(user):
        return DeviceGrant.Authority.STAFF
    return DeviceGrant.Authority.MEMBER


class DeviceGrantCreationRetryRequired(Exception):
    """The consumed first-factor and attestation inputs must be replaced."""


def issue_first_device_session(user, challenge, verified_attestation, *, login_method):
    """Create a new grant atomically, after one-time proof consumption has committed."""
    if challenge is None or verified_attestation is None:
        raise DeviceGrantCreationRetryRequired
    try:
        assert_mobile_grant_creation_enabled()
        now = timezone.now()
        with transaction.atomic():
            user = lock_session_user(user)
            assert_grant_user_allowed(user)
            registration = (
                NativeAppRegistration.objects.select_for_update()
                .filter(
                    eligible_registration_q(), pk=challenge.registration_id,
                    platform=challenge.platform,
                    app_id=challenge.app_id,
                    environment=challenge.environment,
                )
                .first()
            )
            if registration is None:
                raise DeviceGrantCreationRetryRequired
            grant = DeviceGrant.objects.create(
                registration=registration,
                user=user,
                authority=authority_for_login(user, login_method=login_method),
                platform=challenge.platform,
                app_id=challenge.app_id,
                signing_identity=matched_signing_identity(challenge, verified_attestation.metadata),
                environment=challenge.environment,
                attestation_subject_fingerprint=audit_events.fingerprint(
                    verified_attestation.subject
                ),
                attestation_key_id=verified_attestation.metadata.get("key_id"),
                attestation_public_key=verified_attestation.metadata.get("public_key"),
                attested_at=now,
                last_used_at=now,
            )
            access, refresh, _family = issue_device_token_pair(user, grant)
            audit_events.record_auth_event(
                user, "auth.device_login_succeeded", target=user,
                meta={"grant_hash": audit_events.fingerprint(grant.pk)},
            )
    except DeviceSuperadminNotSupported as exc:
        audit_grant_refusal(exc)
        raise
    except AuthenticationFailed as exc:
        raise DeviceGrantCreationRetryRequired from exc
    return access, refresh, grant
