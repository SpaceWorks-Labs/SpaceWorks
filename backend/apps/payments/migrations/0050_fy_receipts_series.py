from django.db import migrations, models


class Migration(migrations.Migration):
    """Parity O-B3: a `receipt` counter series for per-FY receipt numbers while tax is off.

    Adds the choice to the counter and widens the document shape check to the new series. No data moves:
    the series starts empty and only fills once a space switches `billing.fy_receipts` on.
    """

    dependencies = [
        ('payments', '0049_money_three_decimals'),
    ]

    operations = [
        migrations.AlterField(
            model_name='documentnumbercounter',
            name='series',
            field=models.CharField(
                choices=[('invoice', 'Tax invoice / receipt'), ('credit_note', 'Credit note'), ('receipt', 'Receipt')],
                max_length=16),
        ),
        migrations.RemoveConstraint(model_name='paymentdocument', name='document_series_shape'),
        migrations.AddConstraint(
            model_name='paymentdocument',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(('fy_start__isnull', True), ('number_series', '')),
                    models.Q(('fy_start__isnull', False), ('number_series__in', ['invoice', 'credit_note', 'receipt'])),
                    _connector='OR'),
                name='document_series_shape'),
        ),
    ]
