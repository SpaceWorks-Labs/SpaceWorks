"""Stage B over every alias of the person: merged shells, account keys and merge records.

A merge leaves the source account behind as an inert shell (``merged_into`` the person)
that keeps immutable history and the UNIQUE_RESOLVE losers (calendar feeds, endpoints,
deliveries, preferences). Deleting the person therefore purges every id in
``staff_identity.actor_ids_for``:

- each tenant scrub also scrubs every shell's tenant-local copies (``scrub_tenant``);
- the global step deletes what the shells still hold and scrubs every merge record's PII
  snapshot under ``app.account_purge_user_id`` (``purge_alias_globals``);
- the person's account keys are destroyed first (``shred_account_keys``), so a snapshot
  sealed under the per-account key is unreadable even in an older backup.

The retained set is unchanged: audit, payments, evidence and the other immutable history
stay on their (shell) actor ids.
"""

import logging

from django.db import connection

from apps.accounts.account_deletion_discovery import _model, aliases

logger = logging.getLogger(__name__)
SHELL_LEFTOVERS = (
    ("bookings.BookingCalendarFeed", "user"),
    ("integrations.NotificationEndpointChallenge", "user"),
    ("integrations.NotificationEndpoint", "user"),
    ("integrations.MessagingDelivery", "user"),
    ("integrations.PushDevice", "user"),
    ("notifications.NotificationInboxRow", "user"),
)


def shred_account_keys(user):
    """Erase the saved-details vault and destroy the account keys of every alias.

    Runs outside any transaction (the erasure takes its own fences). Returns False when
    the erasure could not finish, so the global step waits for a later sweep.
    """
    from apps.encryption.account_models import AccountPiiKey

    for account in aliases(user):
        if not AccountPiiKey.objects.filter(user_id=account.pk).exists():
            continue
        from apps.accounts.saved_details.lifecycle import erase_account_vault
        try:
            erase_account_vault(account.pk, actor=None)
        except Exception as exc:
            logger.warning("account_key_shred_failed", extra={
                "user_id": user.pk, "alias_id": account.pk, "error_type": type(exc).__name__})
            return False
    return True


def purge_alias_globals(user, global_rows):
    """Caller holds the person's lock inside the final global transaction."""
    shells = aliases(user)[1:]
    for shell in shells:
        global_rows(shell)
    ids = [shell.pk for shell in shells]
    if ids:
        for label, owner in SHELL_LEFTOVERS:
            model = _model(label)
            if model is not None:
                model._base_manager.filter(**{f"{owner}_id__in": ids}).delete()
    scrub_merge_records([user.pk, *ids])
    return len(ids)


def scrub_merge_records(ids):
    """Scrub the PII snapshot of every merge record naming one of ``ids``.

    The record trigger admits exactly this write, and only for an account named in the
    record that ``app.account_purge_user_id`` identifies.
    """
    from django.db.models import Q

    from apps.accounts.models_account_merge import AccountMergeRecord

    ids = set(ids)
    rows = AccountMergeRecord.objects.filter(Q(source_id__in=ids) | Q(target_id__in=ids)).exclude(
        snapshot_scheme=AccountMergeRecord.SnapshotScheme.SCRUBBED).order_by("created_at", "pk")
    count = 0
    for record in rows:
        owner = record.target_id if record.target_id in ids else record.source_id
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_purge_user_id', %s, true)", [str(owner)])
        AccountMergeRecord.objects.filter(pk=record.pk).update(
            snapshot_scheme=AccountMergeRecord.SnapshotScheme.SCRUBBED, snapshot_ciphertext="",
            snapshot_key_version=None)
        count += 1
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.account_purge_user_id', '', true)")
    return count
