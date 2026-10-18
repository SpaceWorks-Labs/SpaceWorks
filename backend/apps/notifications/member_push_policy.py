"""Canonical source/recipient policy plus attested device/account context."""
from django.core.exceptions import ValidationError

from apps.integrations.notification_resolution import eligible, resolve
from apps.notifications.inbox_scope import validate_notification_scope


def recipient_allowed(envelope):
    try:
        validate_notification_scope(envelope.scope)
    except ValidationError:
        return False
    return (envelope.audience in {"member", "requester", "staff"}
            and eligible(envelope) and any(target.channel == "native_push" for target in resolve(envelope)))


def device_allowed(device, envelope):
    grant, user = device.device_grant, envelope.recipient
    registration = grant.registration
    account_ok = (user.is_active and user.access_status == "active" and not user.is_tenant_dump_stub
                  and user.retired_at is None and user.deletion_requested_at is None
                  and user.account_purged_at is None)
    context_ok = (
        user.account_kind == "member" and grant.authority == "member" and grant.staff_makerspace_id is None
        if envelope.audience in {"member", "requester"} else
        user.account_kind == "staff" and user.staff_makerspace_id == envelope.makerspace_id
        and grant.authority == "staff" and grant.staff_makerspace_id == envelope.makerspace_id
        and grant.login_method == "password"
    )
    return bool(
        account_ok and context_ok and device.active
        and device.invalidated_at is None
        and device.makerspace_id == envelope.makerspace_id and device.user_id == user.pk
        and grant.status == "active" and grant.revoked_at is None and grant.user_id == user.pk
        and grant.credential_generation == user.credential_generation
        and registration.status == "approved" and registration.revoked_at is None
        and registration.makerspace_id in (None, envelope.makerspace_id)
        and grant.app_id == registration.app_id and grant.platform == registration.platform
        and grant.environment == registration.environment == device.environment
        and device.provider == ("apns" if grant.platform == "apple" else "fcm")
        and grant.platform in {"apple", "android"} and grant.attested_at is not None
        and grant.signing_identity and grant.attestation_subject_fingerprint
        and (not registration.signing_identities or grant.signing_identity in registration.signing_identities)
    )
