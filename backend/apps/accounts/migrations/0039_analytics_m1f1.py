"""Phase 1f-1 tracking; no historical rows are backfilled."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0038_account_restore'), ('makerspaces', '0093_fixed_roles_constraint')]

    operations = [
        migrations.CreateModel(name='DeviceActivityDay', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('grant', models.ForeignKey("accounts.DeviceGrant", on_delete=models.CASCADE)),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)),
            ('platform', models.CharField(max_length=16)),
            ('local_day', models.DateField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'constraints': [models.UniqueConstraint(
            fields=["grant", "makerspace", "local_day"], nulls_distinct=False,
            name="unique_grant_space_activity_day",
        )]}),
        migrations.CreateModel(name='AttestationVerificationLog', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('platform', models.CharField(max_length=16)),
            ('mode', models.CharField(max_length=32)),
            ('outcome', models.CharField(max_length=16, choices=[
        ("sent", "Verified"), ("failed", "Rejected"), ("skipped", "Unavailable"),
    ])),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={}),
    ]
