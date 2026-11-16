from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0017_l12_consumables_expected_back"),
        ("hardware_requests", "0031_plain_admin_names"),
        ("makerspaces", "0134_loan_context_generations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EquipmentKitTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("revision", models.PositiveBigIntegerField(default=1)),
                ("current_version", models.PositiveIntegerField(default=1)),
                ("published_for_contexts", models.BooleanField(default=False)),
                ("archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
            ],
        ),
        migrations.CreateModel(
            name="EquipmentKitVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=200)),
                ("lines", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="inventory.equipmentkittemplate")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("template", "version"), name="uniq_equipment_kit_version")]},
        ),
        migrations.CreateModel(
            name="EquipmentConsumablePlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lines", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("borrower", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("kit_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentkitversion")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
            ],
        ),
        migrations.CreateModel(
            name="EquipmentKitAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lines", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("kit_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentkitversion")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="hardware_requests.hardwarerequest")),
            ],
        ),
        migrations.CreateModel(
            name="EquipmentProposalReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_id", models.UUIDField()),
                ("fingerprint_version", models.PositiveSmallIntegerField(default=2)),
                ("payload_sha256", models.CharField(max_length=64)),
                ("intent_snapshot", models.TextField()),
                ("intent_version", models.PositiveSmallIntegerField(default=2)),
                ("outcome_kind", models.CharField(choices=[("request", "Request"), ("consumable_plan", "Consumable plan")], max_length=24)),
                ("imported_nonreplayable", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("borrower", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("creator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("consumable_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentconsumableplan")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
                ("request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="hardware_requests.hardwarerequest")),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("makerspace", "operation_id"), name="uniq_equipment_proposal_op"),
                models.CheckConstraint(condition=(models.Q(creator__isnull=False) | models.Q(imported_nonreplayable=True)), name="equipment_proposal_creator_or_sticky"),
                models.CheckConstraint(condition=(models.Q(request__isnull=False, consumable_plan__isnull=True) | models.Q(request__isnull=True, consumable_plan__isnull=False)), name="equipment_proposal_one_result"),
            ]},
        ),
    ]
