import apps.payments.money_model
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Decision 342: machine sessions and service requests logged with the event they were done for."""

    dependencies = [
        ("events", "0099_team_join_declined"),
        ("machines", "0040_certifications_to_access_grants"),
        ("makerspaces", "0154_retire_printing_module"),
        ("payments", "0051_ledgerentry_plural"),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineEventLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("requester", "Given by the requester"),
                                                     ("adapter", "Given by an adapter session"),
                                                     ("manager", "Logged by the area manager")], max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name="machine_use_links", to="events.event")),
                ("machine_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                   to="machines.machinetype")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("service_request", models.OneToOneField(blank=True, null=True,
                                                         on_delete=django.db.models.deletion.CASCADE,
                                                         related_name="event_link",
                                                         to="machines.machineservicerequest")),
                ("session", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="event_link", to="machines.machinesession")),
            ],
        ),
        migrations.AddIndex(
            model_name="machineeventlink",
            index=models.Index(fields=["makerspace", "event"], name="machine_event_link_event_idx"),
        ),
        migrations.AddConstraint(
            model_name="machineeventlink",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("service_request__isnull", True), ("session__isnull", False)),
                                   models.Q(("service_request__isnull", False), ("session__isnull", True)),
                                   _connector="OR"),
                name="machine_event_link_one_subject"),
        ),
        migrations.CreateModel(
            name="MachineEventCostApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("approved", "Approved to charge to the event"),
                                                       ("withdrawn", "Approval withdrawn")], max_length=10)),
                ("amount", apps.payments.money_model.MoneyDecimalField(blank=True, decimal_places=3, max_digits=13,
                                                                      null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("link", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="cost_approvals", to="events.machineeventlink")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name="+", to="payments.payment")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="machineeventcostapproval",
            constraint=models.CheckConstraint(condition=models.Q(("amount__isnull", True), ("amount__gte", 0),
                                                                _connector="OR"),
                                              name="machine_event_cost_not_negative"),
        ),
    ]
