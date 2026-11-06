"""Creation-only device authority policy; existing grants retain refresh access."""

from django.utils.translation import gettext
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
from apps.accounts.session_issuance import lock_session_user
from apps.accounts.staff_identity import is_person, is_platform


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
    if is_platform(user) or user.is_superuser or user.role == User.Role.SUPERADMIN:
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


def authority_for_login(user, *, login_method, staff_makerspace_id=None, event_id=None):
    """Member authority for any person; staff authority is a step-up (Q12): a fixed
    makerspace where the person holds a staff role, proven with a real second factor
    under ``require_staff_mfa``, after any primary login method. Provenance comes from
    the issuer or the server-owned MFA context, never from request data."""
    assert_grant_user_allowed(user)
    if not is_person(user):
        raise AuthenticationFailed(gettext("Invalid device authorization."))
    if event_id is not None and staff_makerspace_id is None:
        from apps.accounts.services_event_grants import event_authority_for_login
        return event_authority_for_login(user, event_id)
    if staff_makerspace_id is None:
        return DeviceGrant.Authority.MEMBER
    from apps.accounts.mfa_policy import VERIFIED, source_for
    from apps.accounts.staff_identity import has_staff_role, require_staff_mfa
    if not has_staff_role(user, staff_makerspace_id):
        raise AuthenticationFailed(gettext("Staff access is required for this makerspace."))
    if source_for(user) != VERIFIED:
        raise AuthenticationFailed(gettext("Native staff sessions require a verified second factor."))
    require_staff_mfa(user, None)
    return DeviceGrant.Authority.STAFF


class DeviceGrantCreationRetryRequired(Exception):
    """The consumed first-factor and attestation inputs must be replaced."""


def issue_first_device_session(user, challenge, verified_attestation, *, login_method, staff_makerspace_id=None):
    """Create a new grant atomically, after one-time proof consumption has committed."""
    if challenge is None or verified_attestation is None:
        raise DeviceGrantCreationRetryRequired
    try:
        assert_mobile_grant_creation_enabled()
        with transaction.atomic():
            user = lock_session_user(user)
            grant = create_device_grant(user, challenge, metadata=verified_attestation.metadata,
                subject_hash=audit_events.fingerprint(verified_attestation.subject), login_method=login_method,
                staff_makerspace_id=staff_makerspace_id)
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


def create_device_grant(user, challenge, *, metadata, subject_hash, login_method, staff_makerspace_id=None,
                        event_id=None):
    """Caller holds User; every first grant uses this registration/provenance policy."""
    now = timezone.now()
    assert_grant_user_allowed(user)
    authority = authority_for_login(user, login_method=login_method, staff_makerspace_id=staff_makerspace_id,
                                    event_id=event_id)
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
    if (registration is None or authority == DeviceGrant.Authority.STAFF
            and registration.makerspace_id not in (None, staff_makerspace_id)):
        raise AuthenticationFailed(gettext("Device registration is no longer approved."))
    if authority == DeviceGrant.Authority.EVENT:
        from apps.accounts.services_event_grants import assert_registration_for_event
        assert_registration_for_event(registration, event_id)
    grant = DeviceGrant.objects.create(
        registration=registration,
        user=user,
        authority=authority,
        staff_makerspace_id=staff_makerspace_id if authority == DeviceGrant.Authority.STAFF else None,
        event_id=event_id if authority == DeviceGrant.Authority.EVENT else None,
        credential_generation=user.credential_generation,
        login_method=login_method,
        platform=challenge.platform,
        app_id=challenge.app_id,
        signing_identity=matched_signing_identity(challenge, metadata),
        environment=challenge.environment,
        attestation_subject_fingerprint=subject_hash,
        attestation_key_id=metadata.get("key_id"),
        attestation_public_key=metadata.get("public_key"),
        attested_at=now,
        last_used_at=now,
    )
    if authority == DeviceGrant.Authority.STAFF:
        from apps.accounts.services_staff_grants import audit_issued
        audit_issued(user, grant)
    elif authority == DeviceGrant.Authority.EVENT:
        from apps.accounts.services_event_grants import audit_issued as audit_event_issued
        audit_event_issued(user, grant)
    return grant
