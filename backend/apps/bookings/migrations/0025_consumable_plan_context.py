from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0024_loan_context"),
        ("inventory", "0018_equipment_proposals"),
        ("makerspaces", "0134_loan_context_generations"),
    ]
    operations = [
        migrations.CreateModel(
            name="BookingConsumablePlanContext",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="bookings.booking")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
                ("plan", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentconsumableplan")),
            ],
        ),
    ]
