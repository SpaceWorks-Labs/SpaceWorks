"""Transaction-local, bounded access to semantic-reference provenance."""

import json

from .transaction_state import require_import_transaction

TABLE_NAME = "tenant_import_reference_state"
EQUIPMENT_RETAINED_FIELD = "__equipment_materialized_v1__"
EQUIPMENT_INTENT_LABELS = frozenset({"events.Event", "events.EventRegistration", "bookings.Booking", "hardware_requests.LoanWaitlistEntry", "hardware_requests.HardwareRequest", "inventory.InventoryProduct", "inventory.EquipmentKitTemplate", "inventory.EquipmentKitAllocation", "inventory.EquipmentConsumablePlan", "operations.InventoryAdjustment"})


class ReferenceState:
    def __init__(self, archive, *, using="default"):
        self.archive = archive
        self.connection = require_import_transaction(using)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TEMPORARY TABLE {TABLE_NAME} (
                    source_model_label text NOT NULL,
                    source_object_id text NOT NULL,
                    field_name text NOT NULL,
                    kind text NOT NULL,
                    detail jsonb NOT NULL,
                    PRIMARY KEY (source_model_label, source_object_id, field_name)
                ) ON COMMIT DROP
                """
            )
        self._load(archive)

    def _load(self, archive):
        batch = []
        for record in archive.json_lines("migration/reference_provenance.jsonl"):
            if record["field_name"] == EQUIPMENT_RETAINED_FIELD:
                from .insertion_errors import ArchiveFormatError
                raise ArchiveFormatError("Archive uses a reserved internal reference key.")
            batch.append(
                (
                    record["source_model_label"],
                    str(record["source_object_id"]),
                    record["field_name"],
                    record["kind"],
                    json.dumps(record.get("detail", {})),
                )
            )
            if len(batch) == 500:
                self._insert(batch)
                batch.clear()
        if batch:
            self._insert(batch)
        batch = []
        for record in archive.json_lines("migration/external_references.jsonl"):
            if record["field_name"] == EQUIPMENT_RETAINED_FIELD:
                from .insertion_errors import ArchiveFormatError
                raise ArchiveFormatError("Archive uses a reserved internal reference key.")
            batch.append(
                (
                    record["source_model_label"],
                    str(record["source_object_id"]),
                    record["field_name"],
                    "external_reference",
                    json.dumps(record),
                )
            )
            if len(batch) == 500:
                self._insert(batch)
                batch.clear()
        if batch:
            self._insert(batch)

    def _insert(self, batch):
        with self.connection.cursor() as cursor:
            cursor.executemany(
                f"""
                INSERT INTO {TABLE_NAME}
                    (source_model_label, source_object_id, field_name, kind, detail)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                batch,
            )

    def get(self, model_label, source_object_id, field_name):
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT kind, detail FROM {TABLE_NAME}
                WHERE source_model_label=%s AND source_object_id=%s AND field_name=%s
                """,
                [model_label, str(source_object_id), field_name],
            )
            row = cursor.fetchone()
        if row is None:
            return None
        # Django's psycopg2 backend decodes jsonb at the FIELD layer, not the
        # connection layer, so a raw cursor hands back the column as text. Every
        # existing consumer only tested this record for existence, which is why a
        # string detail went unnoticed until a caller first read into it.
        detail = row[1]
        return {
            "kind": row[0],
            "detail": json.loads(detail) if isinstance(detail, str) else detail,
        }

    def has_any(self, model_label, source_object_ids, field_name):
        """One indexed lookup for a bounded caller-supplied batch of source IDs."""
        if not source_object_ids:
            return False
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {TABLE_NAME} WHERE source_model_label=%s "
                "AND field_name=%s AND source_object_id=ANY(%s) LIMIT 1",
                [model_label, field_name, [str(value) for value in source_object_ids]],
            )
            return cursor.fetchone() is not None

    def record_equipment_materialized(self, label, pairs):
        """Record only source/target pairs actually inserted in this transaction."""
        if label not in EQUIPMENT_INTENT_LABELS:
            raise ValueError("Unexpected equipment intent target model.")
        self._insert([(label, str(source), EQUIPMENT_RETAINED_FIELD, "equipment_materialized",
                       json.dumps({"target_pk": str(target)})) for source, target in pairs])

    def equipment_materialized(self, label, source, target):
        if label not in EQUIPMENT_INTENT_LABELS:
            return False
        record = self.get(label, source, EQUIPMENT_RETAINED_FIELD)
        return bool(record and record["kind"] == "equipment_materialized" and record["detail"] == {"target_pk": str(target)})

    def bind_equipment_identities(self, identities):
        self._equipment_identities = identities

    def equipment_identity_resolved(self, source, target):
        identities = getattr(self, "_equipment_identities", None)
        return bool(identities and identities.was_resolved(source, target))

    def external_snapshot(self, model_label, source_object_id, field_name):
        """Return a closure snapshot only when the record declares that shape."""
        record = self.get(model_label, source_object_id, field_name)
        if record is None or record["kind"] != "external_reference":
            return None
        return record["detail"]["snapshot"]

    def count(self):
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            return cursor.fetchone()[0]
