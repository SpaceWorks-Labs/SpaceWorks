"""P1b (owner decision #111 Q8): drop the dead B1 merge branch from accounts_guard_context.

backup/0032 dropped `backup_b1_staff_shell_restore` and nothing creates the
`spaceworks_b1_merge` role any more, so the branch that called it can never run.
This restores the 0033 body. Reverse reinstates the 0035 body verbatim; PL/pgSQL
resolves the dropped function lazily, so that body still compiles.
"""

from importlib import import_module

from django.db import migrations

_GUARDED = import_module("apps.accounts.migrations.0035_as_p4_guarded_shell_restore")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0047_platform_pii_access_grant")]

    operations = [migrations.RunSQL(_GUARDED.REVERSE, _GUARDED.SQL)]
