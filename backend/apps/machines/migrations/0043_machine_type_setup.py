"""Decision 343 follow-up: per-type booking defaults, training notes and member-visible documents per space."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0042_seed_consumable_profiles"),
        ("makerspaces", "0091_fixed_roles_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineTypeSetup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("booking_slot_minutes", models.PositiveIntegerField(blank=True, null=True, validators=[
                    django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(1440)])),
                ("booking_buffer_before_minutes", models.PositiveIntegerField(
                    blank=True, null=True, validators=[django.core.validators.MaxValueValidator(1440)])),
                ("booking_buffer_after_minutes", models.PositiveIntegerField(
                    blank=True, null=True, validators=[django.core.validators.MaxValueValidator(1440)])),
                ("booking_approval_mode", models.CharField(blank=True, choices=[
                    ("", "Not set"), ("instant", "Instant confirmation"), ("approve", "Staff approval required")],
                    default="", max_length=8)),
                ("training_notes", models.TextField(blank=True)),
                ("notes_at_session_start", models.BooleanField(default=True)),
                ("notes_at_job_request", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("machine_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="space_setups", to="machines.machinetype")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="machine_type_setups", to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="machinetypesetup",
            constraint=models.UniqueConstraint(fields=("makerspace", "machine_type"), name="machine_type_setup_unique"),
        ),
        migrations.CreateModel(
            name="MachineTypeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("object_key", models.CharField(max_length=255, unique=True)),
                ("original_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=100)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("member_visible", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("machine_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="space_documents", to="machines.machinetype")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="machine_type_documents", to="makerspaces.makerspace")),
            ],
            options={"ordering": ["title", "id"]},
        ),
    ]
