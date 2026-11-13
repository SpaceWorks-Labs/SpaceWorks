import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('makerspaces', '0142_fundraising_role_seed'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='makerspacemembershipsettings',
            name='joining_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='communitypolicy',
            name='volunteer_credit_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=11, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='daypassproduct',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=11, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='makerspace',
            name='membership_dues_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13,
        decimal_places=3,
        default=0,
        validators=[django.core.validators.MinValueValidator(0)],
    ),
        ),
        migrations.AlterField(
            model_name='membershipplan',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13, decimal_places=3, default=0, validators=[django.core.validators.MinValueValidator(0)]
    ),
        ),
        migrations.AlterField(
            model_name='membershipplan',
            name='renewal_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13, decimal_places=3, null=True, blank=True, validators=[django.core.validators.MinValueValidator(0)]
    ),
        ),
        migrations.AlterField(
            model_name='membershipplan',
            name='joining_fee',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13, decimal_places=3, null=True, blank=True, validators=[django.core.validators.MinValueValidator(0)]
    ),
        ),
        migrations.AlterField(
            model_name='membershipterm',
            name='price',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='membershipterm',
            name='joining_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='membershiprequest',
            name='joining_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='membershiprequest',
            name='first_term_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='volunteercredit',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=11, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='volunteercredit',
            name='applied_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=11, decimal_places=3, null=True, blank=True),
        ),
        # Reversal runs the operations backwards, so the drop must also come last to precede the first undo.
        drop_views_operation(),
    ]
