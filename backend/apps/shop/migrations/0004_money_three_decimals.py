import apps.payments.money_model
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('shop', '0003_shop_event_offer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shopvariant',
            name='price',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='shoporder',
            name='subtotal',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporder',
            name='discount_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporder',
            name='total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporder',
            name='tax_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporder',
            name='amount_due',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporderline',
            name='unit_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='shoporderline',
            name='discount_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporderline',
            name='line_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='shoporderline',
            name='taxable_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporderline',
            name='tax_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shoporderreturn',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shopcashsession',
            name='opening_float',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='shopcashsession',
            name='counted_cash',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='shopcashsession',
            name='expected_cash',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='shopcashsession',
            name='variance',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
    ]
