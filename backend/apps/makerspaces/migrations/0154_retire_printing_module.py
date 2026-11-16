"""Fold the retired `printing` module key into `machine_service` (decision 340b, 0.12.0).

Machine service handles service requests for every machine type, the 3D print queue
included. A space with `printing` installed keeps machine service on and loses only the
separate key; a space without it is left alone. One `makerspace.module_retired` audit row
per folded space. Reversible: the reverse restores each folded space's exact module list
from that audit row (see `migration_support.retire_printing_module`).

Anything that still carries `printing` after this -- an older backup or tenant dump, an API
client -- is read through `makerspaces.module_aliases` as `machine_service`.
"""

from django.db import migrations

from apps.makerspaces.migration_support.retire_printing_module import backwards, forwards


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0153_account_profile_merge"),
        ("audit", "0009_audit_verification_runs"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
