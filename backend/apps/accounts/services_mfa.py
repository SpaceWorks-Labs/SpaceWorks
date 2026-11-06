"""Locked MFA credential changes. Refusals commit counters before raising."""

from django.utils.translation import gettext
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password

from apps.accounts import audit_events, security_signals
from apps.accounts.login_security_contract import LAST_FACTOR
from apps.accounts.mfa_crypto import matching_step, recovery_codes
from apps.accounts.mfa_policy import assert_available, has_passkey, required, stamp
from apps.accounts.passkeys.policy import passkeys_usable
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.services_tokens import blacklist_outstanding_tokens
from apps.makerspaces.secrets import decrypt_value, encrypt_value


def active(user):
    if (not user.is_active or user.is_tenant_dump_stub or user.is_walk_in or user.retired_at is not None
            or user.deletion_requested_at is not None
            or user.access_status != User.AccessStatus.ACTIVE):
        raise AuthenticationFailed(gettext("Account is not available."))
    from apps.accounts.principal_guards import refuse_anonymous_requester_credential
    from apps.backup.recovery import assert_token_issuance_allowed
    refuse_anonymous_requester_credential(user)
    assert_token_issuance_allowed(user)


def consume_code(row, code):
    step = matching_step(decrypt_value(row.secret), code, timezone.now().timestamp(), row.last_step)
    if step is not None:
        row.last_step = step
        row.save(update_fields=["last_step"])
        return True
    for index, digest in enumerate(row.recovery_digests):
        if check_password(code, digest):
            row.recovery_digests = row.recovery_digests[:index] + row.recovery_digests[index + 1:]
            row.save(update_fields=["recovery_digests"])
            audit_events.record_auth_event(row.user, "auth.mfa_recovery_used", target=row.user)
            return True
    return False


def enable(user, row, secret, code, *, keep_grant=None):
    step = matching_step(secret, code, timezone.now().timestamp())
    if step is None:
        return None
    codes, digests = recovery_codes()
    row.secret = encrypt_value(secret)
    row.enabled_at = timezone.now()
    row.last_step = step
    row.recovery_digests = digests
    row.version = uuid.uuid4()
    row.save()
    blacklist_outstanding_tokens(user, keep_grant=keep_grant)
    meta = {"delivery": "device", "grant_hash": audit_events.fingerprint(keep_grant.pk)} if keep_grant else None
    audit_events.record_auth_event(user, "auth.mfa_enabled", target=user, meta=meta)
    stamp(user, row)
    from apps.accounts.mfa_grace import close_grace
    close_grace(user)
    security_signals.send_mfa_changed(user, security_signals.TOTP_ENABLED)
    return codes


@transaction.atomic
def change(user, password, *, disable=False):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not disable:
        assert_available(user)
    active(user)
    if not user.check_password(password):
        raise AuthenticationFailed(gettext("Password verification failed."))
    row = UserMFA.objects.select_for_update().get(user=user)
    passkeys = has_passkey(user)
    # Recovery codes back a passkey too, so a passkey-only account may regenerate them.
    if not (row.enabled_at or (passkeys and not disable)):
        raise PermissionDenied(gettext("MFA is not enrolled."))
    if disable and required(user) and not (passkeys and passkeys_usable(user)):
        # Staff MFA is mandatory (#62): a passkey may replace the authenticator, never nothing.
        raise PermissionDenied({"detail": gettext("Staff need a second factor. Add a passkey before removing "
                                          "the authenticator."), "code": LAST_FACTOR})
    row.version = uuid.uuid4()
    if disable:
        codes = []
        row.secret, row.enabled_at, row.last_step = "", None, -1
        if not passkeys:
            row.recovery_digests = []
    else:
        codes, row.recovery_digests = recovery_codes()
    row.save()
    blacklist_outstanding_tokens(user)
    audit_events.record_auth_event(user, "auth.mfa_disabled" if disable else "auth.mfa_recovery_regenerated",
                                   target=user)
    security_signals.send_mfa_changed(
        user, security_signals.TOTP_DISABLED if disable else security_signals.RECOVERY_REGENERATED)
    return codes
