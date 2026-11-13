"""Decision 221(d): membership plans include booking / machine-time hours per term."""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0134_loan_context_generations")]
    operations = [
        migrations.AddField(
            model_name="membershipplan", name="included_booking_hours",
            field=models.PositiveIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(8784)]),
        ),
        migrations.AddField(
            model_name="membershipplan", name="included_machine_hours",
            field=models.PositiveIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(8784)]),
        ),
    ]
