"""Fold the retired module keys into per-parent capabilities, and grant today's editors.

Owner decisions #97, #128 C-9 and C-11b. Every space keeps exactly what it had:

* `maintenance` installed -> `machines.maintenance` on;
* `procurement` installed -> `inventory.tobuy` on, and `machines.tobuy` on where
  `machines` is installed (today's To-Buy list covers both kinds);
* warranty rows on assets -> `inventory.warranty`; on machines (with `machines`
  installed) -> `machines.warranty`;
* the two old keys are stripped from `enabled_modules`; no row of any table is touched.
  Each retired key is audited per space as `makerspace.module_retired`.

Then every person who could edit a domain's settings through `domain_settings` -- an
active membership (or active organization grant) holding that domain's manager action,
without `manage_makerspace` -- receives a per-person grant, audited as
`settings.grant_created` with `via=migration`. New spaces start with no grants.

The rules below are frozen copies on purpose: a migration must not follow later edits of
the live registries. Not reversed: switching capabilities back is an operator decision.
"""

from django.db import migrations

from apps.makerspaces.migration_support.fold_modules import (  # noqa: F401 - direct-call tests
    editors, fold, folded_capabilities, forwards, grant,
)


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0110_settings_authority"),
        ("audit", "0009_audit_verification_runs"),
        ("organizations", "0007_events_programme_schema"),
        ("warranty", "0003_remove_printer_host"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
