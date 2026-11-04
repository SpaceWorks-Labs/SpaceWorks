"""Per-space security policy (lane S0, #110c/#128 C-2): one row of policy-backed values per space."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('makerspaces', '0117_membership_lifecycle_backfill'),
    ]

    operations = [
        migrations.CreateModel(
            name='MakerspaceSecurityPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('values', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('makerspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='security_policy', to='makerspaces.makerspace')),
            ],
        ),
    ]
