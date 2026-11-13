import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('maintenance', '0011_incident_area_inventory_label'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='maintenancelog',
            name='cost',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13, decimal_places=3, null=True, blank=True,
    ),
        ),
        migrations.AlterField(
            model_name='issuereport',
            name='quote_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='issueevent',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='subjectmaintenancelog',
            name='cost',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
    ]
