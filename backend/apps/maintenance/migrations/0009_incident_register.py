"""The safety incident register and its follow-up actions (decision 223 (k)). Additive only."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user():
    return models.ForeignKey(
        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
        to=settings.AUTH_USER_MODEL)


def _link(to, related_name="+"):
    return models.ForeignKey(
        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name=related_name, to=to)


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0008_issue_report_machine_session"),
        ("machines", "0035_consumable_cost_shop_sources"),
        ("bookings", "0028_booking_is_house"),
        ("hardware_requests", "0031_plain_admin_names"),
        ("events", "0091_event_staff_invite_limits"),
        ("makerspaces", "0137_guest_passes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Incident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(
                    choices=[("incident", "Incident"), ("near_miss", "Near miss")], default="incident", max_length=10)),
                ("severity", models.CharField(
                    choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
                    default="low", max_length=10)),
                ("status", models.CharField(
                    choices=[("reported", "Reported"), ("triaged", "Triaged"), ("in_progress", "In progress"),
                             ("resolved", "Resolved"), ("closed", "Closed")], default="reported", max_length=12)),
                ("area", models.CharField(
                    choices=[("machines", "Machines"), ("lending", "Lending"), ("events", "Events"),
                             ("bookings", "Rooms and bookings"), ("other", "Other (Space Manager only)")],
                    default="other", max_length=10)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, max_length=200)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("involved_note", models.CharField(blank=True, max_length=200)),
                ("resolution_note", models.TextField(blank=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", _link("bookings.booking")),
                ("event", _link("events.event")),
                ("guest_pass", _link("makerspaces.guestpass")),
                ("involved_user", _user()),
                ("loan", _link("hardware_requests.hardwarerequest")),
                ("machine", _link("machines.machine", "incidents")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="incidents",
                    to="makerspaces.makerspace")),
                ("repair_issue", _link("maintenance.issuereport", "incidents")),
                ("reporter", _user()),
                ("room", _link("bookings.bookablespace", "incidents")),
                ("sponsor_user", _user()),
                ("triaged_by", _user()),
            ],
            options={"ordering": ["-occurred_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["makerspace", "status", "occurred_at"], name="incident_space_status_idx"),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["makerspace", "area"], name="incident_space_area_idx"),
        ),
        migrations.CreateModel(
            name="IncidentAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=300)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assignee", _user()),
                ("created_by", _user()),
                ("done_by", _user()),
                ("incident", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="maintenance.incident")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
