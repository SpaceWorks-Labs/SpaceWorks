import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('events', '0091_event_staff_invite_limits'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='hackathonprize',
            name='amount_per_winner',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprize',
            name='estimated_value',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprogrammeoptions',
            name='deposit_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprogrammeoptions',
            name='entry_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprogrammeoptions',
            name='team_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprizepayout',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='hackathonprizepayout',
            name='tds_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='hackathonprizepayout',
            name='net_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='hackathonprizeshare',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='hackathonprizeoutcome',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='eventaddon',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='event',
            name='payment_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13,
        decimal_places=3,
        default=0,
        validators=[django.core.validators.MinValueValidator(0)],
    ),
        ),
        migrations.AlterField(
            model_name='eventsalessettings',
            name='booking_fee_fixed',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventsalessettings',
            name='cancellation_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventorder',
            name='subtotal',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventorder',
            name='discount_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventorder',
            name='fee_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventorder',
            name='total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventorderline',
            name='unit_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='eventorderline',
            name='discount_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventorderline',
            name='line_total',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='eventorderdue',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='eventpasstype',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventpasstype',
            name='occurrence_refund_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0,
                                                   validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventpromocode',
            name='amount_off',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventregistration',
            name='quoted_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='eventregistration',
            name='discount_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='eventseries',
            name='payment_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]
    ),
        ),
        migrations.AlterField(
            model_name='eventtickettype',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventtickettype',
            name='min_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='eventvenuefee',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True,
                                 validators=[django.core.validators.MinValueValidator(0)]),
        ),
        # Reversal runs the operations backwards, so the drop must also come last to precede the first undo.
        drop_views_operation(),
    ]
