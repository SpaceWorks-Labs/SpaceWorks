"""Phase 1f-1 tracking; no historical rows are backfilled."""
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('inventory', '0014_public_terms_and_watch'), ('makerspaces', '0093_fixed_roles_constraint')]

    operations = [
        migrations.CreateModel(name='InventoryStockSnapshot', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)),
            ('product', models.ForeignKey("inventory.InventoryProduct", on_delete=models.CASCADE)),
            ('local_day', models.DateField()),
            ('available', models.PositiveIntegerField()),
            ('issued', models.PositiveIntegerField()),
            ('total', models.PositiveIntegerField()),
            ('out_of_stock', models.BooleanField()),
            ('below_reorder', models.BooleanField()),
        ], options={'constraints': [models.UniqueConstraint(fields=["product", "local_day"], name="unique_product_stock_day")]}),
        migrations.AddField(model_name='inventoryproduct', name='unit_cost', field=models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])),
        migrations.AddField(model_name='inventoryproduct', name='cost_currency', field=models.CharField(max_length=3, blank=True)),
        migrations.AddField(model_name='inventoryproduct', name='cost_unit', field=models.CharField(max_length=16, blank=True)),
        migrations.RunSQL(sql="CREATE FUNCTION inventory_tracking_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$\nBEGIN\n    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN\n        RETURN OLD;\n    END IF;\n    RAISE EXCEPTION 'tracking facts are append-only';\nEND;\n$$;\nCREATE TRIGGER inventorystocksnapshot_immutable BEFORE UPDATE OR DELETE ON inventory_inventorystocksnapshot FOR EACH ROW EXECUTE FUNCTION inventory_tracking_reject_mutation();\n", reverse_sql='DROP TRIGGER IF EXISTS inventorystocksnapshot_immutable ON inventory_inventorystocksnapshot;\nDROP FUNCTION IF EXISTS inventory_tracking_reject_mutation();'),
    ]
