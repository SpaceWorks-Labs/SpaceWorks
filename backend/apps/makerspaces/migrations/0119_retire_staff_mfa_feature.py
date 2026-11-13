"""Retire ``security.staff_mfa_required`` (release 2, S-A; owner decision #62).

Staff MFA is mandatory for every staff role in every space, so the per-space switch is
gone: strip the key from ``enabled_features``, delete its platform locks and write one
``makerspace.capability_retired`` audit row per affected space. Reverse is a no-op: the
switch no longer exists to restore.
"""

from django.db import migrations

from apps.makerspaces.migration_support.retire_staff_mfa import retire


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0118_security_policy"),
        ("audit", "0009_audit_verification_runs"),
    ]

    operations = [migrations.RunPython(retire, migrations.RunPython.noop)]
