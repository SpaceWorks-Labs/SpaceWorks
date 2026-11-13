import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('machines', '0036_induction_and_supervised_sessions'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='makerspacemachinetypepricing',
            name='rate_per_unit',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='makerspacemachinetypepricing',
            name='flat_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='makerspacemachinetypepolicy',
            name='quote_above_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='machineservicerequest',
            name='payment_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        # Reversal runs the operations backwards, so the drop must also come last to precede the first undo.
        drop_views_operation(),
    ]
