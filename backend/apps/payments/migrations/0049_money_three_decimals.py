from decimal import Decimal

import apps.payments.money_model
import django.core.validators
from django.db import migrations, models
from apps.analytics.migration_support import drop_views_operation


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('payments', '0048_inventory_loans_labels'),
    ]

    operations = [
        drop_views_operation(),
        migrations.AlterField(
            model_name='donationcampaign',
            name='goal_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='donationpledge',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='donation',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='donationsettings',
            name='minimum_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=1),
        ),
        migrations.AlterField(
            model_name='sponsortier',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='sponsorshipcharge',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='paymentcaptureflag',
            name='captured_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='paymentclaim',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='paymentdispute',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='paymentdisputeevent',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='paymentdocument',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='eventfinancebudget',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='eventmoneysettings',
            name='prize_tds_threshold',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=Decimal("10000.00")),
        ),
        migrations.AlterField(
            model_name='ledgerentry',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='openingbalance',
            name='cash_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='openingbalance',
            name='bank_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='payment',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='pricingdefaultline',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='pricingdefaultline',
            name='cap',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='priceoverride',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='priceoverride',
            name='cap',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='pricediscount',
            name='amount_off',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='refund',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='refundcase',
            name='due_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='refundcase',
            name='approved_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='refundpolicy',
            name='cancellation_fee',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='makerspacepaymentsettings',
            name='loan_deposit_amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='makerspacepaymentsettings',
            name='loan_late_fee_per_day',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='makerspacepaymentsettings',
            name='loan_late_fee_cap',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3, default=0),
        ),
        migrations.AlterField(
            model_name='manualsettlement',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
        migrations.AlterField(
            model_name='settlementconfirmation',
            name='amount',
            field=apps.payments.money_model.MoneyDecimalField(max_digits=13, decimal_places=3),
        ),
    ]
