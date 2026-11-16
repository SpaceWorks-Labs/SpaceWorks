"""Phase 1f-1 tracking; no historical rows are backfilled."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('notifications', '0004_member_push'), ('makerspaces', '0093_fixed_roles_constraint')]

    operations = [
        migrations.AddField(model_name='memberpushdelivery', name='platform', field=models.CharField(max_length=16, blank=True)),
        migrations.AddField(model_name='memberpushdelivery', name='provider_source', field=models.CharField(max_length=8, blank=True)),
    ]
