"""Frozen conversion for accounts 0050: every live staff account becomes a person.

Historical models and the migration-safe audit writer only, so a deployment that jumps
several releases still runs exactly this code against exactly this schema. Lock order
per account: Makerspace -> User -> recovery envelopes.
"""

import json
import uuid

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.unification_plan import assert_acknowledged

SNAPSHOT_FIELDS = ("email", "first_name", "last_name", "display_name", "phone",
                   "phone_e164", "telegram_user_id")
TERMINAL_ENVELOPES = ("consumed", "discarded", "undeliverable", "delivery_unknown")
MODELS = (
    "accounts.User", "accounts.DeviceGrant", "accounts.DeviceRefreshFamily",
    "accounts.DeviceRefreshToken", "accounts.PasswordResetEnvelope", "accounts.StaffInvitation",
    "accounts.MFAChallenge", "accounts.EmailVerificationChallenge",
    "accounts.PhoneVerificationChallenge", "accounts.OidcBrowserAttempt",
    "accounts.SocialLoginNonce", "accounts.ReauthenticationSession",
    "accounts.AccountMergeRecord", "makerspaces.Makerspace", "makerspaces.StationOperatorLease",
    "integrations.PushDevice", "integrations.NotificationEndpoint",
    "integrations.NotificationEndpointChallenge", "token_blacklist.OutstandingToken",
    "token_blacklist.BlacklistedToken", "sessions.Session", "backup.DeploymentRecoveryState",
    "audit.AuditLog", "audit.AuditMacKey",
)


def convert(apps, schema_editor):
    connection = schema_editor.connection
    alias = connection.alias
    plan = assert_acknowledged(connection, getattr(settings, "ACCOUNT_UNIFICATION_ACK", ""))
    models = {label: apps.get_model(label) for label in MODELS}
    run_id, now = uuid.uuid4(), timezone.now()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.account_unification_run_id', %s, true)", [str(run_id)])
    revoke_every_device(models, alias, now)
    for account in plan["staff_accounts"]:
        convert_account(models, alias, account, plan["plan_sha256"], run_id, now)
    _objects(models, "accounts.PasswordResetEnvelope", alias).filter(context="staff").exclude(
        status__in=TERMINAL_ENVELOPES, digest_is_live=False,
    ).update(status="discarded", digest_is_live=False, expires_at=None, superseded_at=now,
             terminal_at=now, claimed_at=None, claim_owner="", claim_expires_at=None)
    _objects(models, "accounts.StaffInvitation", alias).filter(
        accepted_at__isnull=True, revoked_at__isnull=True,
    ).update(revoked_at=now)
    _objects(models, "backup.DeploymentRecoveryState", alias).update(auth_generation=uuid.uuid4())
    with connection.cursor() as cursor:
        # Fire the deferred membership checks now: 0048 alters accounts_user next, and
        # Postgres refuses ALTER TABLE while trigger events are pending.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _objects(models, label, alias):
    return models[label].objects.using(alias)


def revoke_every_device(models, alias, now):
    """Q18/#66: every native grant and family ends, members' included (clean break)."""
    tokens = _objects(models, "accounts.DeviceRefreshToken", alias).filter(blacklisted_at__isnull=True)
    outstanding = _objects(models, "token_blacklist.OutstandingToken", alias).filter(
        jti__in=_objects(models, "accounts.DeviceRefreshToken", alias).values("jti"),
    )
    _blacklist(models, alias, outstanding, now)
    tokens.update(blacklisted_at=now)
    _objects(models, "accounts.DeviceRefreshFamily", alias).filter(revoked_at__isnull=True).update(revoked_at=now)
    grants = _objects(models, "accounts.DeviceGrant", alias).filter(Q(status="active") | Q(revoked_at__isnull=True))
    _objects(models, "integrations.PushDevice", alias).filter(
        device_grant__in=grants.values("pk"), active=True,
    ).update(active=False, invalidated_at=now)
    grants.update(status="revoked", revoked_at=now)


def _blacklist(models, alias, outstanding, now):
    blacklisted = models["token_blacklist.BlacklistedToken"]
    missing = outstanding.exclude(Exists(blacklisted.objects.using(alias).filter(token_id=OuterRef("pk"))))
    blacklisted.objects.using(alias).bulk_create(
        [blacklisted(token_id=pk, blacklisted_at=now) for pk in missing.values_list("pk", flat=True)],
    )


def convert_account(models, alias, account, plan_sha256, run_id, now):
    from apps.accounts.unification_audit import record_conversion
    from apps.makerspaces.secrets import encrypt_value

    if account["makerspace_id"] is not None:
        _objects(models, "makerspaces.Makerspace", alias).select_for_update(no_key=True).filter(
            pk=account["makerspace_id"]).first()
    user = _objects(models, "accounts.User", alias).select_for_update().get(pk=account["id"])
    list(_objects(models, "accounts.PasswordResetEnvelope", alias).select_for_update().filter(
        user_id=user.pk).order_by("pk"))
    snapshot = {field: getattr(user, field) for field in SNAPSHOT_FIELDS}
    changes = {"account_kind": "member", "staff_makerspace": None, "email_verified_at": None,
               "credential_generation": user.credential_generation + 1}
    for field in account["holds"]:
        changes[field] = ""
        if field == "phone_e164":
            changes["phone_verified_at"] = None
    _objects(models, "accounts.User", alias).filter(pk=user.pk).update(**changes)
    counts = revoke_account_credentials(models, alias, user.pk, now)
    _objects(models, "accounts.AccountMergeRecord", alias).create(
        decision="converted", source_id=user.pk, proof_method="migration", run_id=run_id,
        plan_sha256=plan_sha256, snapshot_scheme="deployment",
        snapshot_ciphertext=encrypt_value(json.dumps(snapshot, sort_keys=True)),
        held_fields=account["holds"], roles_kept=account["roles"], counts=counts,
        state="completed", completed_at=now,
    )
    record_conversion(account["makerspace_id"], user.pk, holds=account["holds"],
                      roles_kept=sorted({slug for row in account["roles"] for slug in row["roles"]}),
                      models=models, alias=alias)


def revoke_account_credentials(models, alias, user_id, now):
    """The database half of ``revoke_all_credentials`` for one converted account."""
    from django.contrib.sessions.backends.db import SessionStore

    counts = {"django_sessions": 0}
    decoder = SessionStore()
    for session in _objects(models, "sessions.Session", alias).iterator():
        if str(decoder.decode(session.session_data).get("_auth_user_id", "")) == str(user_id):
            _objects(models, "sessions.Session", alias).filter(pk=session.pk).delete()
            counts["django_sessions"] += 1
    outstanding = _objects(models, "token_blacklist.OutstandingToken", alias).filter(user_id=user_id)
    counts["outstanding_tokens"] = outstanding.count()
    _blacklist(models, alias, outstanding, now)
    for name, label, owner in (
        ("mfa_challenges", "accounts.MFAChallenge", "user_id"),
        ("email_challenges", "accounts.EmailVerificationChallenge", "user_id"),
        ("phone_challenges", "accounts.PhoneVerificationChallenge", "user_id"),
        ("oidc_attempts", "accounts.OidcBrowserAttempt", "intended_user_id"),
        ("social_nonces", "accounts.SocialLoginNonce", "device_grant__user_id"),
        ("endpoint_challenges", "integrations.NotificationEndpointChallenge", "user_id"),
    ):
        counts[name] = _objects(models, label, alias).filter(
            **{owner: user_id, "consumed_at__isnull": True}).update(consumed_at=now)
    counts["reauthentication_proofs"] = _objects(models, "accounts.ReauthenticationSession", alias).filter(
        user_id=user_id).update(auth_time=None, social_verified_at=None, enrollment_confirmed_at=None,
                                credential_fingerprint="")
    counts["station_operator_leases"] = _objects(models, "makerspaces.StationOperatorLease", alias).filter(
        actor_id=user_id, revoked_at__isnull=True).update(revoked_at=now)
    counts["notification_endpoints"] = _objects(models, "integrations.NotificationEndpoint", alias).filter(
        user_id=user_id, revoked_at__isnull=True).update(revoked_at=now, verification_state="revoked")
    counts["push_devices"] = _objects(models, "integrations.PushDevice", alias).filter(
        user_id=user_id, active=True).update(active=False, invalidated_at=now)
    counts["staff_invitations"] = _objects(models, "accounts.StaffInvitation", alias).filter(
        account_id=user_id, accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
    return counts
