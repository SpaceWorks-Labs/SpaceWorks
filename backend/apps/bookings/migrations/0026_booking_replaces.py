from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("bookings", "0025_consumable_plan_context")]
    operations = [
        migrations.AddField(
            model_name="booking",
            name="replaces",
            field=models.OneToOneField(blank=True, editable=False, null=True,
                                       on_delete=django.db.models.deletion.SET_NULL,
                                       related_name="replaced_by", to="bookings.booking"),
        ),
    ]
