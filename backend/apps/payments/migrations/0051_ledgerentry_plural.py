from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("payments", "0050_fy_receipts_series")]

    operations = [
        migrations.AlterModelOptions(
            name="ledgerentry",
            options={"ordering": ["-entry_date", "-pk"], "verbose_name_plural": "ledger entries"},
        ),
    ]
