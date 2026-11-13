"""P1b (owner decisions #110/#111): drop archive recipients, custody and activation.

Superadmin is always on, so every archive is encrypted to the platform key alone.
Order: the archive freeze guard stops reading the access snapshot (0031 drops the
column); the two custody guard functions go (CASCADE drops their triggers); the
decision-snapshot constraint goes; then the tables, dependants first. Reverse
recreates the tables (empty) and their guards; dropped rows are not restored.
"""

from importlib import import_module

from django.db import migrations


FREEZE_GUARD_WITHOUT_ACCESS = r"""
CREATE OR REPLACE FUNCTION backup_archive_freeze_fields_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.backup_run_id IS NOT NULL
       AND NEW.backup_run_id IS DISTINCT FROM OLD.backup_run_id THEN
        RAISE EXCEPTION 'immutable backup archive backup_run cannot be updated';
    END IF;

    IF OLD.status <> 'pending'
       AND NEW.backup_run_id IS DISTINCT FROM OLD.backup_run_id THEN
        RAISE EXCEPTION 'backup archive backup_run cannot change after claim';
    END IF;

    IF OLD.expires_at IS NOT NULL
       AND NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
        RAISE EXCEPTION 'immutable backup archive expiry cannot be updated';
    END IF;

    RETURN NEW;
END;
$$;
"""


def _freeze_guard_with_access():
    source = import_module(
        "apps.backup.migrations.0024_archive_promotion_fencing"
    ).ARCHIVE_FREEZE_SQL
    start = source.index("CREATE OR REPLACE FUNCTION backup_archive_freeze_fields_guard")
    end = source.index("$$;", source.index("AS $$", start) + 5) + 3
    return source[start:end]


DROP_CUSTODY_GUARDS = r"""
DROP FUNCTION IF EXISTS backup_reject_reservation_mutation() CASCADE;
DROP FUNCTION IF EXISTS backup_component_recipient_guard() CASCADE;
"""


def _restore_custody_guards():
    reservation = import_module(
        "apps.backup.migrations.0004_makerspace_archive_recipients"
    ).Migration.operations[-1].sql
    guards = import_module("apps.backup.migrations.0014_b1_artifact_ledger_guards").GUARDS
    start = guards.index("CREATE OR REPLACE FUNCTION backup_component_recipient_guard()")
    return reservation + "\n" + guards[start:]


class Migration(migrations.Migration):
    dependencies = [("backup", "0029_managed_staging")]

    operations = [
        migrations.RunSQL(FREEZE_GUARD_WITHOUT_ACCESS, _freeze_guard_with_access()),
        migrations.RunSQL(DROP_CUSTODY_GUARDS, _restore_custody_guards()),
        migrations.RemoveConstraint(
            model_name="backuparchive",
            name="backup_makerspace_decision_snapshot_present",
        ),
        migrations.DeleteModel(name="ArchiveCustodyAlarmDelivery"),
        migrations.DeleteModel(name="TenantExitCustodyAlarmDelivery"),
        migrations.DeleteModel(name="MakerspaceArchiveCustodyState"),
        migrations.DeleteModel(name="MakerspaceTenantExitCustodyState"),
        migrations.DeleteModel(name="ArchiveRecipientReservation"),
        migrations.DeleteModel(name="BackupComponentRecipient"),
        migrations.DeleteModel(name="B1ActivationState"),
        migrations.DeleteModel(name="MakerspaceArchiveRecipient"),
    ]
