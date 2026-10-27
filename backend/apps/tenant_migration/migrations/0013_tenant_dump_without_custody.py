"""P1b (owner decision #111 Q7): a tenant-exit capture no longer snapshots the
superadmin-access decision. The platform key always seals the outer envelope, and
`frozen_tenant_recipients` now holds the one-shot `--recipient` keys."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("tenant_migration", "0012_brokerless_import_run")]

    operations = [
        migrations.RemoveField(
            model_name="tenantdumpcapture", name="superadmin_access_at_decision"
        ),
    ]
