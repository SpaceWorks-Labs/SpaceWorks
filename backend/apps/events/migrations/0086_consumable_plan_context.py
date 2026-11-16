from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0085_loan_context"),
        ("inventory", "0018_equipment_proposals"),
        ("makerspaces", "0134_loan_context_generations"),
    ]
    operations = [
        migrations.CreateModel(
            name="EventConsumablePlanContext",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="makerspaces.makerspace")),
                ("participant_registration", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="events.eventregistration")),
                ("plan", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="inventory.equipmentconsumableplan")),
            ],
        ),
    ]
