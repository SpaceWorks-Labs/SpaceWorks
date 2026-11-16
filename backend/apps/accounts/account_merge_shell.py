"""The two writes that end a merge: the immutable merge record and the inert shell (U-C).

The record keeps the source's original identity as ciphertext under the survivor's
per-account key (``encryption/account_models``) so the account purge can crypto-shred it;
the deployment field key is used only when account keys are not configured here. The shell
reuses ``staff_retirement.shell_values`` with a ``merged-<uuid>`` username and must be
written under the caller's ``app.account_unification_run_id``.
"""

import json
import uuid

from apps.accounts.models_account_merge import AccountMergeRecord as Record

SNAPSHOT_FIELDS = ("username", "email", "first_name", "last_name", "display_name", "phone",
                   "phone_e164", "telegram_user_id")


def record(survivor, source, intent, run_id, preview, counts, key, now):
    snapshot = json.dumps({field: getattr(source, field) for field in SNAPSHOT_FIELDS}, sort_keys=True)
    record_id = uuid.uuid4()
    if key is not None:
        from apps.encryption.account_crypto import encrypt
        scheme, version = Record.SnapshotScheme.ACCOUNT, key.version
        ciphertext = encrypt(snapshot.encode(), key.dek, key_version=key.version, user_id=survivor.pk,
                             table=Record._meta.db_table, pk=str(record_id), field="snapshot_ciphertext")
    else:
        from apps.makerspaces.secrets import encrypt_value
        scheme, version, ciphertext = Record.SnapshotScheme.DEPLOYMENT, None, encrypt_value(snapshot)
    return Record.objects.create(
        id=record_id, decision=Record.Decision.MERGED, source=source, target=survivor,
        proof_method=intent.method, run_id=run_id, snapshot_scheme=scheme, snapshot_key_version=version,
        snapshot_ciphertext=ciphertext, roles_kept=preview["privilege_diff"]["roles_gained"],
        counts=counts, state=Record.State.COMPLETED, completed_at=now)


def shell(source, survivor, now):
    from apps.accounts.models import User
    from apps.makerspaces.staff_retirement import shell_values

    values = shell_values(source.pk, None)
    values.update(username=f"merged-{uuid.uuid4().hex}", account_kind="staff", merged_into_id=survivor.pk,
                  merged_at=now, credential_generation=source.credential_generation + 1,
                  password="!merged-account")
    User._base_manager.filter(pk=source.pk).update(**values)


def open_grace(survivor, preview, now):
    """#128 C-1: the survivor becomes staff with no factor -> one 3-day grace (never a second)."""
    if not preview["grace_opens"]:
        return False
    from apps.accounts.login_security_contract import GRACE_MERGE, STAFF_MFA_GRACE
    from apps.accounts.models_mfa_grace import StaffMfaGrace

    _row, created = StaffMfaGrace.objects.get_or_create(user=survivor, defaults={
        "started_at": now, "source": GRACE_MERGE, "ends_at": now + STAFF_MFA_GRACE})
    return created
