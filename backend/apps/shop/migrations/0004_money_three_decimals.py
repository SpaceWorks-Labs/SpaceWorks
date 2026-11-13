import apps.payments.money_model
import django.core.validators
from django.db import migrations, models


def drop_analytics_views(apps, schema_editor):
    """A curated analytics view blocks ALTER TYPE on the money columns it reads.

    `manage.py migrate` drops the views first (analytics `pre_migrate_drop`) and rebuilds them
    afterwards; a bare MigrationExecutor (tests, tooling) sends no pre_migrate signal, so the
    alter, in either direction, must not depend on it. Dropping is idempotent and the views
    are derived objects that `analytics_sync` rebuilds.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    from apps.analytics import db_ddl

    with schema_editor.connection.cursor() as cursor:
        db_ddl.drop_view_schemas(cursor)


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('shop', '0003_shop_event_offer'),
    ]

    operations = [
        migrations.RunPython(drop_analytics_views, drop_analytics_views),
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
