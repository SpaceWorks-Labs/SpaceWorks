from django.db import migrations, models


class Migration(migrations.Migration):
    """Open item B12: an independent switch that keeps the non-member on-site waiver gate on without guest passes."""

    dependencies = [
        ('makerspaces', '0143_money_three_decimals'),
    ]

    operations = [
        migrations.AddField(
            model_name='guestpasspolicy',
            name='waiver_gate_without_passes',
            field=models.BooleanField(default=False),
        ),
    ]
