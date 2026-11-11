from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0019_equipment_snapshot_guards"),
        ("operations", "0017_plain_admin_names"),
        ("makerspaces", "0134_loan_context_generations"),
    ]
    operations = [
        migrations.CreateModel(
            name="EquipmentConsumableUseReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_id", models.UUIDField()),
                ("quantity", models.PositiveIntegerField()),
                ("payload_sha256", models.CharField(max_length=64)),
                ("intent_snapshot", models.TextField()),
                ("intent_version", models.PositiveSmallIntegerField(default=2)),
                ("imported_nonreplayable", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("adjustment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="operations.inventoryadjustment")),
                ("creator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("allocation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentkitallocation")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentconsumableplan")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="inventory.inventoryproduct")),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("makerspace", "operation_id"), name="uniq_equipment_use_op"),
                models.CheckConstraint(condition=(models.Q(creator__isnull=False) | models.Q(imported_nonreplayable=True)), name="equipment_use_creator_or_sticky"),
                models.CheckConstraint(condition=(models.Q(allocation__isnull=False, plan__isnull=True) | models.Q(allocation__isnull=True, plan__isnull=False)), name="equipment_use_one_source"),
            ]},
        ),
        migrations.RunSQL(
            sql="CREATE TRIGGER equipment_use_receipt_immutable BEFORE UPDATE OR DELETE ON inventory_equipmentconsumableusereceipt FOR EACH ROW EXECUTE FUNCTION inventory_equipment_snapshot_guard();",
            reverse_sql="DROP TRIGGER IF EXISTS equipment_use_receipt_immutable ON inventory_equipmentconsumableusereceipt;",
        ),
    ]
