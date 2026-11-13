import apps.payments.money_model
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Money columns store thousandths (0.001) so KWD/BHD/OMR/JOD/TND keep their fils.

    Widening numeric(12,2) to numeric(13,3) changes no value: 12.35 is 12.350.
    """

    dependencies = [
        ('bookings', '0029_booking_organization_link'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookablespace',
            name='payment_amount',
            field=apps.payments.money_model.MoneyDecimalField(
        max_digits=13,
        decimal_places=3,
        default=0,
        validators=[django.core.validators.MinValueValidator(0)],
    ),
        ),
    ]
