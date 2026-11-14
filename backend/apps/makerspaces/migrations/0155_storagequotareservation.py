from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0154_retire_printing_module")]

    operations = [migrations.CreateModel(
        name="StorageQuotaReservation",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("object_key", models.CharField(max_length=512, unique=True)),
            ("final_key", models.CharField(max_length=512)),
            ("staging_key", models.CharField(max_length=560)),
            ("bucket", models.CharField(max_length=255)),
            ("final_bucket", models.CharField(max_length=255)),
            ("storage_endpoint", models.CharField(blank=True, max_length=512)),
            ("kind", models.CharField(max_length=20)),
            ("size_bytes", models.PositiveBigIntegerField()),
            ("converted", models.BooleanField(default=False)),
            ("cleaning", models.BooleanField(default=False)),
            ("released", models.BooleanField(default=False)),
            ("expires_at", models.DateTimeField(db_index=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("makerspace", models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to="makerspaces.makerspace")),
        ],
    )]
