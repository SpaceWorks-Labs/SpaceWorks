"""Roll one makerspace back to a per-space archive in ONE database transaction.

The caller owns the transaction, the makerspace row lock and the source gate. Inside it:
immutable-row deletion is authorized for this transaction only (the
``app.allow_immutable_delete`` GUC: foreign keys stay on and deferred), the space's
dataset rows are replaced by the archive's with identical primary keys, append-only
records are kept, and every reference into a removed row is resolved or blocks
(``space_restore_graph``). Any failure rolls every row back.
"""

from collections import defaultdict

from django.apps import apps
from django.db import DatabaseError, connection

from apps.tenant_migration.dependency_order import topologically_sort_models

from .space_restore_graph import raw_delete, resolve
from .space_restore_plan import (
    KEPT_LIVE,
    MAKERSPACE_KEEP_LIVE,
    SpaceRestoreError,
    live_queryset,
    prepared_record,
    restorable_labels,
)
from .space_restore_users import UserRemap, rescrub_deleted_accounts


def apply_space_restore(makerspace, archive):
    """Replace ``makerspace``'s rows with ``archive``'s; return the restore report."""
    if archive.makerspace_id != makerspace.pk:
        raise SpaceRestoreError("wrong_space", "The archive belongs to a different makerspace.")
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        # Staff memberships are replaced (deleted and re-inserted with the same id); the
        # account guards admit that only inside this exact tenant's purge context.
        cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)",
                       [str(makerspace.pk)])
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    blocked = staff_without_restored_membership(makerspace, archive)
    if blocked:
        raise SpaceRestoreError("staff_after_restore_point",
                                "Staff accounts created after the restore point must be retired first.")
    labels = restorable_labels()
    models = topologically_sort_models([apps.get_model(label) for label in (*labels, *KEPT_LIVE)])
    users = UserRemap(makerspace)
    report = {"replaced": {}, "restored": {}, "kept_live": {}}
    # Ownership predicates join through parents (a registration through its event), so
    # every live set is read, and every reference into a removed row resolved, BEFORE any
    # row is deleted.
    live = {label: set(live_queryset(label, makerspace.pk).values_list("pk", flat=True)) for label in labels}
    gone = {label: live[label] - archive.pks(label) for label in labels}
    outcome = resolve(makerspace.pk, gone, apply=True)
    if outcome.blocked:
        raise SpaceRestoreError("dangling_references", "Rows outside this space still point at rows the restore removes.")
    for label in labels:
        raw_delete(apps.get_model(label), live[label])
        report["replaced"][label] = len(live[label])
    for model in models:
        report["restored"][model._meta.label] = _insert(model, archive, makerspace, users)
    _restore_makerspace_row(makerspace, archive, users)
    _relink_external(archive)
    report.update(outcome.summary())
    report["removed"] = {label: len(pks) for label, pks in gone.items() if pks}
    report["accounts_rescrubbed"] = rescrub_deleted_accounts(makerspace, users.referenced)
    report["users_reattributed"] = users.reattributed
    report["merges_followed"] = users.followed_merges
    _rebuild_blind_indexes(makerspace)
    try:
        with connection.cursor() as cursor:
            # Prove every deferred key and membership rule now, as a typed failure.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    except DatabaseError as exc:
        raise SpaceRestoreError("integrity_check_failed",
                                f"The restored rows do not satisfy a database rule: {str(exc).splitlines()[0][:300]}") from None
    return report


def staff_without_restored_membership(makerspace, archive):
    """Live staff of this space whose one required membership the archive does not carry."""
    from apps.accounts.models import User

    archived = {int(row["fields"]["user"]) for row in archive.rows("makerspaces.MakerspaceMembership")}
    return list(User.objects.filter(account_kind="staff", staff_makerspace=makerspace, retired_at__isnull=True)
                .exclude(pk__in=archived).order_by("pk").values_list("pk", "username"))


def _insert(model, archive, makerspace, users):
    label = model._meta.label
    rows = archive.rows(label)
    if label in KEPT_LIVE:
        live = set(model._base_manager.filter(pk__in=[row["pk"] for row in rows]).values_list("pk", flat=True))
        rows = [row for row in rows if model._meta.pk.to_python(row["pk"]) not in live]
    quote = connection.ops.quote_name
    count = 0
    with connection.cursor() as cursor:
        for record in rows:
            columns, values = prepared_record(model, users.remap(model, record), connection)
            try:
                cursor.execute(
                    f"INSERT INTO {quote(model._meta.db_table)} ({', '.join(quote(c) for c in columns)}) "
                    f"VALUES ({', '.join(['%s'] * len(values))})",
                    values,
                )
            except DatabaseError as exc:  # the whole transaction rolls back; name the row

                raise SpaceRestoreError("integrity_check_failed", f"{label} row {record['pk']} cannot be restored: "
                                        f"{str(exc).splitlines()[0][:240]}") from None
            count += 1
    return count


def _restore_makerspace_row(makerspace, archive, users):
    rows = archive.rows("makerspaces.Makerspace")
    if len(rows) != 1:
        raise SpaceRestoreError("archive_unreadable", "The archive must carry exactly one makerspace row.")
    record = users.remap(makerspace.__class__, rows[0])
    record = {**record, "fields": {name: value for name, value in record["fields"].items()
                                   if name not in MAKERSPACE_KEEP_LIVE}}
    columns, values = prepared_record(makerspace.__class__, record, connection)
    pairs = [(column, value) for column, value in zip(columns, values, strict=True)
             if column != makerspace._meta.pk.column]
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {quote(makerspace._meta.db_table)} SET "
            + ", ".join(f"{quote(column)} = %s" for column, _value in pairs)
            + f" WHERE {quote(makerspace._meta.pk.column)} = %s",
            [value for _column, value in pairs] + [makerspace.pk],
        )


def _relink_external(archive):
    """Re-apply cross-space makerspace links the slice nulled at its boundary (#113)."""
    from apps.makerspaces.models import Makerspace

    pending = defaultdict(list)
    for item in archive.external_references():
        if "field_preimage" not in item or "row_pk" not in item:
            continue
        label, field_name = item["type"].rsplit(".", 1)
        if label.lower() == "operations.stocktransfer" and field_name in {"source", "destination"}:
            field_name = f"{field_name}_makerspace"
        pending[(label, field_name)].append((item["row_pk"], item["field_preimage"]))
    live_spaces = set(Makerspace.objects.values_list("pk", flat=True))
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for (label, field_name), items in pending.items():
            model = apps.get_model(label)
            if model._meta.label in KEPT_LIVE:
                continue
            column = model._meta.get_field(field_name).column
            for row_pk, related in items:
                if related in live_spaces:
                    cursor.execute(
                        f"UPDATE {quote(model._meta.db_table)} SET {quote(column)} = %s "
                        f"WHERE {quote(model._meta.pk.column)} = %s", [related, row_pk],
                    )


def _rebuild_blind_indexes(makerspace):
    from apps.encryption.models import PiiBlindIndex
    from apps.tenant_migration.blind_indexes import rebuild_blind_indexes

    PiiBlindIndex.objects.filter(makerspace=makerspace).delete()
    rebuild_blind_indexes(makerspace)
