from django.db import migrations, models


class Migration(migrations.Migration):
    # Choices only: a finance-ledger receipt photo (lane L5). The column is unchanged.
    dependencies = [("evidence", "0008_receipt_storage_identity")]

    operations = [
        migrations.AlterField(
            model_name="evidencephoto",
            name="evidence_type",
            field=models.CharField(
                choices=[("issue", "Issue"), ("return", "Return"), ("receipt", "Receipt")], max_length=20
            ),
        ),
    ]
