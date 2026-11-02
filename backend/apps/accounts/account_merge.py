"""The account-merge engine: one atomic transaction per (survivor, source) pair (#65; U-C).

Only a PROVED intent merges (``account_merge_proofs``). Under the locks (Makerspaces
ascending -> survivor -> source -> reset envelopes) the engine re-checks every refusal and
the preview digest, revokes every source credential, then walks ``merge_registry`` row by
row: REPOINT moves, KEEP_ON_SHELL stays, UNIQUE_RESOLVE moves unless the survivor holds
the slot (the loser stays on the shell, revoked). The source becomes an inert shell
(``staff_retirement.shell_values`` with a ``merged-<uuid>`` username, ``merged_into`` the
survivor) under the unification GUC, and one immutable ``AccountMergeRecord(merged)``
keeps its original identity as ciphertext. Old audit rows are untouched (their row MAC
covers ``actor_id``, which never changes). The source's factor never moves (Q3); when the
survivor becomes staff with no factor, the 3-day staff-MFA grace opens (#128 C-1).
"""

import uuid

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from apps.accounts import account_merge_walk as walk
from apps.accounts.account_merge_eligibility import (
    MERGE_NOT_ALLOWED, PREVIEW_STALE, PROOF_EXPIRED, TENANT_GATED, MergeRefused, require_survivor,
    source_email, source_refusal,
)
from apps.accounts.account_merge_shell import open_grace, record, shell
from apps.accounts.models_account_merge import AccountMergeIntent as Intent

_REFUSAL_TEXT = {"already_merged": "That account is already linked.",
                 MERGE_NOT_ALLOWED: "These accounts cannot be linked."}


def confirm(request, intent_id, preview_sha256):
    from apps.accounts import reauthentication
    from apps.accounts.staff_identity import has_elevated_authority, require_staff_mfa

    survivor = request.user
    require_survivor(survivor)
    reauthentication.require_recent_reauth(request)
    if has_elevated_authority(survivor):
        require_staff_mfa(survivor, getattr(request, "auth", None))
    try:
        walk.assert_classified()
    except walk.UnclassifiedReference:
        raise MergeRefused(MERGE_NOT_ALLOWED, "Linking accounts is unavailable on this server.") from None
    key = _snapshot_key(survivor)
    result, addresses = _merge(survivor.pk, intent_id, preview_sha256, key)
    from apps.accounts.account_merge_mail import send_linked
    transaction.on_commit(lambda: send_linked(addresses))
    return result


def _snapshot_key(survivor):
    """The survivor's per-account key, prepared outside the transaction, or ``None``
    (deployment key) when account keys are not configured on this server."""
    from apps.encryption.account_services import prepare_account_key
    from apps.encryption.crypto import PiiUnavailable

    try:
        return prepare_account_key(survivor.pk)
    except (PiiUnavailable, RuntimeError):
        return None


def _spaces(*user_ids):
    from apps.backup.capture_managers import every_row
    from apps.makerspaces.models import MakerspaceMembership

    return sorted(set(every_row(MakerspaceMembership).filter(user_id__in=user_ids)
                      .values_list("makerspace_id", flat=True)))


def _lock_spaces(ids):
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    for pk in ids:
        try:
            assert_write_allowed(pk)
        except SourceMigrationGateClosed:
            raise MergeRefused(TENANT_GATED, "A makerspace of one account is temporarily unavailable.") from None
    list(Makerspace.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


@transaction.atomic
def _merge(survivor_id, intent_id, preview_sha256, key):
    from apps.accounts.account_merge_preview import build
    from apps.accounts.account_merge_proofs import locked_intent
    from apps.accounts.credential_revocation import revoke_all_credentials
    from apps.accounts.models import PasswordResetEnvelope, User

    survivor = User.objects.get(pk=survivor_id)
    intent = locked_intent(survivor, intent_id)
    now = timezone.now()
    if intent.state != Intent.State.PROVED or now >= intent.expires_at or intent.source is None:
        raise MergeRefused(PROOF_EXPIRED, "Prove the other account again.")
    source = intent.source
    spaces = _spaces(survivor.pk, source.pk)
    _lock_spaces(spaces)
    _refuse(source_refusal(source, survivor))
    # The person confirms exactly what they reviewed (before credentials are revoked,
    # which changes the source's session rows but nothing the preview shows).
    if not preview_sha256 or build(survivor, source)["preview_sha256"] != preview_sha256:
        raise MergeRefused(PREVIEW_STALE, "The accounts changed. Review the preview again.")
    revoke_all_credentials(source, reason="account_merge", actor=survivor)
    survivor = User.objects.select_for_update().get(pk=survivor.pk)
    source = User.objects.select_for_update().get(pk=source.pk)
    list(PasswordResetEnvelope.objects.select_for_update().filter(
        user_id__in=[survivor.pk, source.pk]).order_by("user_id", "pk"))
    require_survivor(survivor)
    _refuse(source_refusal(source, survivor))
    if set(_spaces(survivor.pk, source.pk)) != set(spaces):
        raise MergeRefused(PREVIEW_STALE, "The accounts changed. Review the preview again.")
    preview = build(survivor, source)
    addresses = [survivor.email, source_email(source)]
    run_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.account_unification_run_id', %s, true)", [str(run_id)])
    counts = _walk(source.pk, survivor.pk, now)
    merged = record(survivor, source, intent, run_id, preview, counts, key, now)
    shell(source, survivor, now)
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.account_unification_run_id', '', true)")
    _prove_constraints()
    grace = open_grace(survivor, preview, now)
    intent.state, intent.consumed_at = Intent.State.CONSUMED, now
    intent.save(update_fields=["state", "consumed_at"])
    gained = sorted({slug for row in preview["privilege_diff"]["roles_gained"] for slug in row["roles"]})
    from apps.audit import services as audit
    audit.record(survivor, "account.merged", target=survivor, meta={
        "proof_method": intent.method, "source_id": source.pk, "record_id": str(merged.pk),
        "counts": counts, "roles_gained": gained, "grace_opened": grace})
    return {"merged": True, "record_id": merged.pk, "roles_gained": preview["privilege_diff"]["roles_gained"],
            "grace_opened": grace, "counts": counts}, addresses


def _refuse(refusal):
    if refusal is not None:
        raise MergeRefused(refusal, _REFUSAL_TEXT.get(refusal, _REFUSAL_TEXT[MERGE_NOT_ALLOWED]))


def _prove_constraints():
    """Fire the deferred membership/account triggers now, as a typed refusal."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    except IntegrityError:
        raise MergeRefused(MERGE_NOT_ALLOWED, "These accounts cannot be linked automatically.") from None


def _walk(source_id, survivor_id, now):
    """Move what may move. A row the database will not let move (a unique slot, or a guard
    on a row the registry calls mutable) stays on the shell, where ``actor_ids_for`` still
    reads it as the person's; only UNIQUE_RESOLVE losers are revoked."""
    counts = {"repointed": 0, "kept_on_shell": 0, "unique_moved": 0, "unique_kept": 0, "revoked": 0}
    for model, column, disposition in walk.references():
        found = walk.rows(model, column, source_id)
        if disposition == walk.KEEP_ON_SHELL:
            counts["kept_on_shell"] += found.count()
            continue
        if disposition == walk.REPOINT:
            updated = _savepoint(lambda: found.update(**{column: survivor_id}))
            if updated is not None:
                counts["repointed"] += updated
                continue
        unique = disposition == walk.UNIQUE_RESOLVE
        for row in list(found.order_by("pk")):
            moved = not walk.conflicts(model, column, row, survivor_id) and _savepoint(
                lambda: walk.rows(model, column, source_id).filter(pk=row.pk).update(**{column: survivor_id}))
            if moved:
                counts["unique_moved" if unique else "repointed"] += 1
                continue
            counts["unique_kept" if unique else "kept_on_shell"] += 1
            if unique and _savepoint(lambda: walk.revoke_loser(model, row, now)):
                counts["revoked"] += 1
    return counts


def _savepoint(write):
    """Run ``write`` in a savepoint; ``None`` when the database refused it."""
    try:
        with transaction.atomic():
            return write()
    except DatabaseError:
        return None
