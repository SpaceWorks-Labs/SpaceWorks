from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0008_reorder_source_product"),
                    ("machines", "0030_service_notice_markers")]
    operations = [migrations.AddField(
        model_name="tobuyitem", name="source_consumable",
        field=models.ForeignKey(to="machines.machineconsumable", null=True, blank=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="low_stock_to_buy_items"),
    )]
