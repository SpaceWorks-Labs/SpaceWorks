"""Read-only preview of a per-space restore and the live fingerprint apply re-checks.

The preview never writes: it compares the archive with the live space, walks the
references a restore would have to resolve (``space_restore_graph`` in read-only mode)
and lists what is kept and flagged. ``blocked`` is true while any row outside the space
would dangle (#113); the restore cannot be confirmed until that is resolved.
"""

import hashlib

from django.apps import apps
from django.utils.dateparse import parse_datetime

from .space_restore_graph import inbound_edges, resolve, foreign_pks
from .space_restore_plan import KEPT_LIVE, MONEY_LABELS, live_queryset, restorable_labels
from .space_restore_users import user_fk_names

MONEY_LISTED = 200


def live_fingerprint(makerspace):
    """Digest of the live rows a restore replaces or keeps; drift refuses the apply."""
    digest = hashlib.sha256(str(makerspace.pk).encode())
    for label in (*restorable_labels(), *KEPT_LIVE):
        pks = sorted(str(pk) for pk in live_queryset(label, makerspace.pk).values_list("pk", flat=True))
        digest.update(f"\x1e{label}\x1f{len(pks)}\x1f".encode())
        digest.update("\x1f".join(pks).encode())
    return digest.hexdigest()


def compute_preview(makerspace, archive):
    snapshot_at = parse_datetime(str(archive.manifest.get("snapshot_at", "")))
    models, gone, relinked = [], {}, 0
    for label in restorable_labels():
        live = set(live_queryset(label, makerspace.pk).values_list("pk", flat=True))
        archived = archive.pks(label)
        gone[label] = live - archived
        if live or archived:
            models.append({"label": label, "live": len(live), "archived": len(archived),
                           "removed": len(live - archived), "added": len(archived - live)})
        relinked += _foreign_inbound(makerspace.pk, label, archived & live)
    outcome = resolve(makerspace.pk, gone, apply=False)
    from .space_restore_apply import staff_without_restored_membership
    outcome.blocked.extend({"model": "accounts.User", "pk": str(pk), "field": "track",
                            "references": "makerspaces.MakerspaceMembership", "reason": "staff_after_restore_point",
                            "username": username}
                           for pk, username in staff_without_restored_membership(makerspace, archive))
    memberships = next((row for row in models if row["label"] == "makerspaces.MakerspaceMembership"), {})
    return {
        "snapshot_at": snapshot_at.isoformat() if snapshot_at else None,
        "models": models,
        "totals": {
            "archived_rows": sum(row["archived"] for row in models),
            "live_rows": sum(row["live"] for row in models),
            "removed_rows": sum(row["removed"] for row in models),
            "added_rows": sum(row["added"] for row in models),
        },
        "memberships": {"removed": memberships.get("removed", 0), "restored": memberships.get("added", 0)},
        "accounts": _accounts(archive),
        "money_after_restore_point": rows_after_restore_point(makerspace, MONEY_LABELS, snapshot_at),
        "evidence_after_restore_point": len(rows_after_restore_point(makerspace, {"evidence.EvidencePhoto"}, snapshot_at)),
        "objects": _objects(archive),
        "inbound_relinked": relinked,
        **outcome.summary(),
        "blocked": bool(outcome.blocked),
    }


def _foreign_inbound(makerspace_id, label, pks):
    """Rows of other spaces pointing at rows that come back; identity ids re-link them."""
    if not pks:
        return 0
    total = 0
    for model, fk in inbound_edges(label):
        rows = list(model._base_manager.filter(**{f"{fk.attname}__in": list(pks)[:5000]})
                    .values_list("pk", flat=True)[:5000])
        if rows:
            total += len(foreign_pks(makerspace_id, model, rows))
    return total


def _accounts(archive):
    from apps.accounts.models import User

    referenced = set()
    for label in (*restorable_labels(), *KEPT_LIVE, "makerspaces.Makerspace"):
        names = user_fk_names(apps.get_model(label))
        for row in archive.rows(label) if names else ():
            referenced.update(int(row["fields"][name]) for name in names if row["fields"].get(name))
    existing = set(User.objects.filter(pk__in=referenced).values_list("pk", flat=True))
    erased = User.objects.filter(pk__in=existing, deletion_requested_at__isnull=False).count()
    return {"referenced": len(referenced), "reattributed": len(referenced - existing), "erased_since": erased}


def rows_after_restore_point(makerspace, labels, snapshot_at):
    rows = []
    for label in sorted(labels):
        model = apps.get_model(label)
        if snapshot_at is None or not any(field.name == "created_at" for field in model._meta.concrete_fields):
            continue
        queryset = live_queryset(label, makerspace.pk).filter(created_at__gt=snapshot_at).order_by("created_at")
        for row in queryset[:MONEY_LISTED]:
            rows.append({"model": label, "pk": str(row.pk), "created_at": row.created_at.isoformat(),
                         "amount": str(getattr(row, "amount", "") or ""),
                         "currency": getattr(row, "currency", ""), "status": getattr(row, "status", "")})
    return rows


def _objects(archive):
    live = [item for item in archive.objects() if item.get("retention_state") != "expired"]
    return {"count": len(live), "bytes": sum(int(item.get("size") or 0) for item in live)}
