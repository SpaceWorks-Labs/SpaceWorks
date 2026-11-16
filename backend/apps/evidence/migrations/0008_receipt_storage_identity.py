"""Legacy identities require supervised verified binding; never infer after a move."""
from importlib import import_module

from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

previous = import_module("apps.evidence.migrations.0007_abandoned_evidence_upload_cleanup")
GUARD = previous.RECEIPT_GUARD_SQL.replace(
    "IF TG_OP = 'UPDATE' THEN", """IF TG_OP = 'UPDATE' THEN
        IF OLD.storage_identity = '' AND NEW.storage_identity <> ''
           AND current_setting('app.evidence_receipt_bind_id', true) = OLD.id::text
           AND (to_jsonb(NEW) - 'storage_identity') = (to_jsonb(OLD) - 'storage_identity')
           AND EXISTS (SELECT 1 FROM operations_storagecapabilitystate s
                       WHERE s.identity_fingerprint=NEW.storage_identity
                       AND s.logical_role='private'
                       AND s.verified_at > now() - interval '900 seconds') THEN
            RETURN NEW;
        END IF;""", 1)
# Reinstall only the function; the 0007 SQL also declares existing triggers.
GUARD = GUARD.split("CREATE OR REPLACE FUNCTION evidence_photo_key_guard")[0]
GUARD = GUARD[:GUARD.index("CREATE OR REPLACE FUNCTION evidence_reject_reserved_key")] if "CREATE OR REPLACE FUNCTION evidence_reject_reserved_key" in GUARD else GUARD
GUARD = GUARD[:GUARD.index("CREATE TRIGGER")] if "CREATE TRIGGER" in GUARD else GUARD
OLD_GUARD = previous.RECEIPT_GUARD_SQL.split("CREATE TRIGGER")[0]


def preserve_bound_identities(apps, schema_editor):
    if apps.get_model("evidence", "EvidenceAbandonedUploadReceipt").objects.exclude(storage_identity="").exists():
        raise IrreversibleError("Cannot discard permanent late-delete bucket identities.")


class Migration(migrations.Migration):
    dependencies = [("evidence", "0007_abandoned_evidence_upload_cleanup"),
                    ("operations", "0015_storage_history_guards")]
    operations = [
        migrations.AddField(model_name="evidenceabandoneduploadreceipt", name="storage_identity",
                            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.RunSQL(GUARD, OLD_GUARD),
        migrations.RunPython(migrations.RunPython.noop, preserve_bound_identities),
    ]
