"""Release 2 lane L4 (decision 71): the per-space financial-year start month, April by default."""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("makerspaces", "0113_remove_superadmin_access_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="makerspace",
            name="financial_year_start_month",
            field=models.PositiveSmallIntegerField(
                default=4,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(12),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="makerspace",
            constraint=models.CheckConstraint(
                condition=models.Q(("financial_year_start_month__gte", 1), ("financial_year_start_month__lte", 12)),
                name="makerspace_fy_start_month_range",
            ),
        ),
    ]
