from django.db import migrations, models


class Migration(migrations.Migration):
    """Payments audit 0.12.0 B-10: an online order carries the client's Idempotency-Key."""

    dependencies = [
        ('shop', '0004_money_three_decimals'),
    ]

    operations = [
        migrations.AddField(
            model_name='shoporder',
            name='idempotency_key',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddConstraint(
            model_name='shoporder',
            constraint=models.UniqueConstraint(
                condition=models.Q(('idempotency_key', ''), _negated=True),
                fields=('makerspace', 'idempotency_key'), name='shop_order_idempotency_once'),
        ),
    ]
