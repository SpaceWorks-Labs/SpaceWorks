"""Lane L8 (#120, #128 C-26): per-space rotation jobs, search keys and retired browser keys."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("encryption", "0011_finance_envelope_tenant_import"),
        ("makerspaces", "0123_l3_member_cards"),
    ]

    operations = [
        migrations.AddField(
            model_name="piiblindindex", name="space_key_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="KeyRotationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("rotation", "Key rotation"), ("emergency_rekey", "Emergency re-key"), ("search_reindex", "Search key rotation")], max_length=24)),
                ("status", models.CharField(choices=[("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="running", max_length=16)),
                ("from_version", models.PositiveIntegerField(blank=True, null=True)),
                ("to_version", models.PositiveIntegerField()),
                ("rows_done", models.PositiveIntegerField(default=0)),
                ("rows_skipped", models.PositiveIntegerField(default=0)),
                ("cursor", models.JSONField(blank=True, default=dict)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("retained_versions", models.JSONField(blank=True, default=list)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="key_rotation_jobs", to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("-started_at", "-id"),
                "constraints": [models.UniqueConstraint(condition=models.Q(("status", "running")), fields=("makerspace",), name="uniq_running_key_job_per_makerspace")],
            },
        ),
        migrations.CreateModel(
            name="MakerspaceSearchKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("salt", models.BinaryField(max_length=32)),
                ("status", models.CharField(choices=[("building", "Building"), ("active", "Active"), ("retired", "Retired")], default="building", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="search_keys", to="makerspaces.makerspace")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("makerspace", "version"), name="uniq_makerspace_search_key_version"),
                    models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("makerspace",), name="uniq_makerspace_active_search_key"),
                    models.UniqueConstraint(condition=models.Q(("status", "building")), fields=("makerspace",), name="uniq_makerspace_building_search_key"),
                    models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="ck_makerspace_search_key_version"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RetiredPublishableKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("retired_at", models.DateTimeField(auto_now_add=True)),
                ("valid_until", models.DateTimeField()),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retired_publishable_keys", to="makerspaces.makerspace")),
            ],
            options={"indexes": [models.Index(fields=["makerspace", "valid_until"], name="enc_retired_pubkey_valid_idx")]},
        ),
    ]
