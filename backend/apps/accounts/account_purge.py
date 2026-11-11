"""Stage B: one tenant boundary per scrub, platform identity last.

Every step covers every alias of the person (``actor_ids_for``: shells merged into
them), see ``account_purge_aliases``.
"""

from apps.integrations.notification_cutover import guarded

import logging
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounts.account_deletion_discovery import _model, alias_tenant_ids
from apps.accounts.account_purge_aliases import purge_alias_globals, shred_account_keys
from apps.accounts.account_purge_scrub import scrub_email_logs, scrub_tenant
from apps.accounts.models import User
from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress, AppleRevocation
from apps.audit import services as audit
from apps.backup.capture_managers import every_row
from apps.makerspaces.models import Makerspace
from apps.makerspaces.secrets import decrypt_value
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


def deleted_username(user):
    return user.deletion_username or user.username


def recorded_address(user):
    return decrypt_value(user.deletion_email_ciphertext) if user.deletion_email_ciphertext else user.email


@guarded()
def purge_account(user_id, counts):
    # This global-only preparation commits before acquiring any tenant locks.
    # It also recovers departures recorded before Stage B was installed.
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).get(pk=user_id)
        if (user.account_kind != "member" or user.account_purged_at or not user.deletion_requested_at or not user.deletion_purge_after
                or user.deletion_purge_after > timezone.now()):
            return
        if not user.purge_started_at:
            user.purge_started_at = timezone.now()
            user.save(update_fields=["purge_started_at"])
            audit.record(None, "account.purge_started", target=user)
        if not user.deletion_username:
            user.deletion_username = "deleted_" + uuid4().hex
            user.save(update_fields=["deletion_username"])
    expected = alias_tenant_ids(user) | set(AccountPurgeProgress.objects.filter(user=user)
                                    .values_list("makerspace_id", flat=True))
    for tenant in sorted(expected):
        try:
            with fanout_tenant_write(tenant, operation="account_purge", counts=counts) as allowed:
                if not allowed:
                    continue
                _scrub(user_id, tenant)
                from apps.accounts.account_purge_objects import drain
                drain(user, tenant)
                _finish_tenant(user_id, tenant)
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("account_tenant_purge_failed", extra={
                "user_id": user_id, "makerspace_id": tenant, "error_type": type(exc).__name__,
            })
    _finish_global(user_id, expected, counts)


def _scrub(user_id, tenant):
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=tenant)
        user = User.objects.select_for_update(no_key=True).get(pk=user_id)
        progress, _ = AccountPurgeProgress.objects.get_or_create(user=user, makerspace=space)
        if user.account_kind != "member" or not user.deletion_requested_at or user.account_purged_at or progress.done_at:
            return
        scrub_tenant(user, tenant, username=deleted_username(user), address=recorded_address(user))
        audit.record(None, "account.tenant_identity_scrubbed", makerspace=space, target=user)


def _finish_tenant(user_id, tenant):
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=tenant)
        user = User.objects.select_for_update(no_key=True).get(pk=user_id)
        progress = AccountPurgeProgress.objects.select_for_update().get(user=user, makerspace=space)
        if progress.done_at or AccountPurgeObject.objects.filter(
            user=user, makerspace=space, quota_released_at__isnull=True,
        ).exists():
            return
        progress.done_at = timezone.now()
        progress.save(update_fields=["done_at"])
        audit.record(None, "account.tenant_purged", makerspace=space, target=user)


def _ready(user, expected):
    if user.account_kind != "member" or not user.deletion_requested_at or user.account_purged_at:
        return False
    done = set(AccountPurgeProgress.objects.filter(user=user, done_at__isnull=False)
               .values_list("makerspace_id", flat=True))
    if not (expected | alias_tenant_ids(user)).issubset(done):
        return False
    return not AppleRevocation.objects.filter(user=user, done_at__isnull=True).exists()


def _finish_global(user_id, expected, counts):
    if not _ready(User.objects.get(pk=user_id), expected):
        return
    # Destroying the account keys takes its own fences, so it runs before the final
    # transaction; restore is already fenced by purge_started_at.
    if not shred_account_keys(User.objects.get(pk=user_id)):
        counts["failed"] += 1
        return
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).get(pk=user_id)
        if not _ready(user, expected):
            return
        _global_rows(user)
        aliases = purge_alias_globals(user, _global_rows)
        values = dict.fromkeys(("email", "phone", "phone_e164", "first_name", "last_name",
                               "telegram_user_id", "deletion_email_ciphertext",
                               "deletion_username", "restriction_reason"), "")
        values.update(username=deleted_username(user), display_name="Deleted member", email_verified_at=None,
                      phone_verified_at=None, self_registered_at=None, last_login=None,
                      account_purged_at=timezone.now(), is_active=False)
        for key, value in values.items():
            setattr(user, key, value)
        user.save(update_fields=list(values))
        audit.record(None, "account.purged", target=user, meta={"aliases": aliases})
        counts["purged"] += 1


def _global_rows(user):
    from apps.accounts.models import (EmailVerificationChallenge, PhoneVerificationChallenge,
                                     PasswordResetEnvelope, SocialIdentity, MFAChallenge, AccountRestoreIntent,
                                     DeviceActivityDay)
    installation = _model("notifications.BrowserFirebaseInstallation")
    if installation is not None:
        every_row(installation).filter(user=user).delete()
    address = recorded_address(user)
    EmailVerificationChallenge.objects.filter(user=user).delete()
    PhoneVerificationChallenge.objects.filter(user=user).delete()
    MFAChallenge.objects.filter(user=user).delete()
    AccountRestoreIntent.objects.filter(user=user).delete()
    PasswordResetEnvelope.objects.filter(user=user).delete()
    SocialIdentity.objects.filter(user=user).delete()
    for label in ("accounts.WebAuthnCredential", "accounts.WebAuthnCeremony", "accounts.StaffMfaGrace",
                  "accounts.KnownDevice", "accounts.KnownNetwork", "accounts.SecurityAlert"):  # S-B
        every_row(_model(label)).filter(user=user).delete()
    # #196 person bearers (already revoked at departure) and their library-owned OAuth rows.
    for label in ("apiclients.PersonalAccessToken", "apiclients.OAuthConsent",
                  "oauth2_provider.RefreshToken", "oauth2_provider.AccessToken", "oauth2_provider.IDToken",
                  "oauth2_provider.Grant", "oauth2_provider.DeviceGrant"):
        model = _model(label)
        if model is not None:
            every_row(model).filter(user=user).delete()
    # Includes unselected (NULL-makerspace) activity. Wait for every tenant gate
    # before removing this grant-owned history; the revoked grants themselves stay.
    DeviceActivityDay.objects.filter(grant__user=user).delete()
    # Platform-addressed logs have no tenant gate. Tenant logs were scrubbed above.
    scrub_email_logs(user, None, address)
    for label in ("integrations.PushDevice", "notifications.NotificationInboxRow"):
        model = _model(label)
        if model is not None:
            every_row(model).filter(user=user, makerspace__isnull=True).delete()


def purge_deleted_accounts():
    from apps.accounts.apple_revocation import sweep_revocations
    sweep_revocations()
    counts = {"purged": 0, "skipped": 0, "failed": 0}
    ids = User.objects.filter(account_kind="member", deletion_requested_at__isnull=False, deletion_purge_after__lte=timezone.now(),
                              account_purged_at__isnull=True).values_list("pk", flat=True)
    for pk in ids.iterator():
        try:
            purge_account(pk, counts)
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("account_purge_failed", extra={"user_id": pk, "error_type": type(exc).__name__})
    return counts
