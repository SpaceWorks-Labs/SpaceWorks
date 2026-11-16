"""Decision 223 (h): a staff-only house booking has no member booker, no charge and no plan hours."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0027_included_hours_usage")]
    operations = [
        migrations.AddField(
            model_name="booking",
            name="is_house",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=models.Q(("is_house", False), ("member__isnull", True), _connector="OR"),
                name="booking_house_has_no_member",
            ),
        ),
    ]
