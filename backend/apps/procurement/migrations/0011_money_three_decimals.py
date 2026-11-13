import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('procurement', '0010_l22_shop_variant_origin'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='tobuyitem',
            name='estimated_unit_cost',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=11,
        decimal_places=3,
        null=True,
        blank=True,
    ),
        ),
        migrations.AlterField(
            model_name='tobuyitem',
            name='actual_unit_cost',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=11,
        decimal_places=3,
        null=True,
        blank=True,
    ),
        ),
        # Reversal runs the operations backwards, so the drop must also come last to precede the first undo.
        drop_views_operation(),
    ]
