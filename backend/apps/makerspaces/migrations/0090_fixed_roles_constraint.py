from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0089_fixed_roles_data")]

    operations = [
        migrations.AddConstraint(
            model_name="makerspacerole",
            constraint=models.CheckConstraint(
                condition=models.Q(is_default=True, is_protected=True, slug__in=(
                    "space_manager", "inventory_manager", "machine_manager", "event_manager",
                    "booking_manager", "handover", "member",
                )),
                name="makerspacerole_fixed_catalogue",
            ),
        ),
    ]
