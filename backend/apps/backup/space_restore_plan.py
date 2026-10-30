"""What a per-space restore replaces, keeps and reads (owner decisions #111 Q5/Q6, #113).

A per-space archive is the lossless raw tenant slice ``archive_payload._tenant_payload``
writes: every dataset row as stored, with its real primary key and its PII still sealed
under the space's own DEKs (which never leave the database). Restoring it therefore keeps
identical ids, slugs and public codes, and needs no re-encryption.

Not everything rolls back. Accounts are never touched; the live audit history, money
records and evidence photos are append-only and stay as they are (Q5).
"""

import json
from functools import lru_cache
from pathlib import Path

from django.apps import apps

from .raw_projection import canonical_owner_q
from .slice_rows import SLICE_ROW_SPECS

FORMAT = "tenant_slice_v1"

# Accounts are untouched by a space restore; the live audit trail is kept and the
# archive's audit rows are never re-imported.
SKIPPED_APPS = frozenset({"accounts", "token_blacklist", "audit"})
# Append-only records kept exactly as they are live. An archived row is inserted only
# when the live table has lost it. Rows recorded after the restore point are flagged.
KEPT_LIVE = (
    "payments.Payment", "payments.ManualSettlement", "payments.Refund",
    "payments.RefundCase", "payments.PaymentDocument",
    "evidence.EvidencePhoto", "evidence.EvidenceObjectRetentionState",
)
MONEY_LABELS = frozenset(KEPT_LIVE[:5])
# Cross-space participation rows the slice carries only as references, never as rows.
NOT_RESTORED = frozenset({"events.EventCollaborator"})
# Live Makerspace columns a restore never rolls back: lifecycle, accounting, verified
# routing and the principal rows of deleted accounts are re-attributed to.
MAKERSPACE_KEEP_LIVE = frozenset({
    "id", "lifecycle_state", "archived_at", "archived_by", "storage_bytes_used",
    "frontend_domain", "frontend_domain_status", "domain_verification_token",
    "domain_verified_at", "frontend_domain_changed_at", "hidden_from_central_directory",
    "anonymous_requester", "created_by", "created_at",
})


class SpaceRestoreError(RuntimeError):
    """A restore cannot proceed; ``code`` is the typed reason shown to the operator."""

    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def file_name(label):
    return f"{label.lower().replace('.', '_')}.json"


class SpaceArchive:
    """Read-only view of one decrypted per-space archive directory."""

    def __init__(self, root):
        self.root = Path(root)
        self.manifest = self._load(self.root / "manifest.json", dict)
        if self.manifest.get("scope") != "makerspace":
            raise SpaceRestoreError("wrong_scope", "This archive is not a one-space archive.")
        self.makerspace_id = int(self.manifest["makerspace_id"])
        self._rows = {}

    def rows(self, label):
        if label not in self._rows:
            path = self.root / "tenant" / file_name(label)
            self._rows[label] = self._load(path, list) if path.exists() else []
        return self._rows[label]

    def pks(self, label):
        model = apps.get_model(label)
        return {model._meta.pk.to_python(row["pk"]) for row in self.rows(label)}

    def external_references(self):
        path = self.root / "tenant" / "external_references.json"
        return self._load(path, list) if path.exists() else []

    def objects(self):
        return list(self.manifest.get("storage", {}).get("objects", []))

    def object_path(self, item):
        return self.root / "objects" / item["bucket_kind"] / item["key"]

    @staticmethod
    def _load(path, kind):
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise SpaceRestoreError("archive_unreadable", f"{Path(path).name} is unreadable.") from None
        if not isinstance(value, kind):
            raise SpaceRestoreError("archive_unreadable", f"{Path(path).name} has the wrong shape.")
        return value


@lru_cache(maxsize=1)
def restorable_labels():
    """Dataset labels a restore replaces, in a stable order."""
    return tuple(sorted(
        label for label in SLICE_ROW_SPECS
        if label.split(".", 1)[0] not in SKIPPED_APPS
        and label not in KEPT_LIVE and label not in NOT_RESTORED
        and label != "makerspaces.Makerspace"
    ))


def live_queryset(label, makerspace_id):
    model = apps.get_model(label)
    return model._base_manager.filter(canonical_owner_q(SLICE_ROW_SPECS[label][1], makerspace_id))


def prepared_record(model, record, connection):
    """(columns, db values) for one fixture row; refuses a row the schema cannot hold."""
    raw = {model._meta.pk.name: record["pk"], **record["fields"]}
    columns, values = [], []
    try:
        for name, value in raw.items():
            field = model._meta.get_field(name)
            columns.append(field.column)
            values.append(field.get_db_prep_save(field.to_python(value), connection))
    except Exception:
        raise SpaceRestoreError(
            "schema_incompatible",
            f"An archived {model._meta.label} row does not fit this deployment's schema.",
        ) from None
    if model._meta.label == "makerspaces.Makerspace":
        return columns, values  # an UPDATE keeps every column the archive does not carry
    for field in model._meta.concrete_fields:
        if field.column in columns:
            continue
        # A column added after the archive was written takes its declared default.
        if field.has_default():
            value = field.get_default()
        elif field.null:
            value = None
        else:
            raise SpaceRestoreError(
                "schema_incompatible",
                f"{model._meta.label}.{field.name} is newer than the archive and has no default.",
            )
        columns.append(field.column)
        values.append(field.get_db_prep_save(value, connection))
    return columns, values
