"""Decision 550: seed any missing protected Fundraising role, idempotently and reversibly."""

from django.db import migrations

from apps.makerspaces.migration_support.fundraising_role_550 import backwards, forwards


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0155_storagequotareservation"), ("audit", "0009_audit_verification_runs")]
    operations = [migrations.RunPython(forwards, backwards)]
