"""Induction-event links, guest certification grants and supervised machine sessions (decision 223).

Additive only: five new tables, no change to an existing one.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user(null=True, related_name="+", on_delete=django.db.models.deletion.SET_NULL, blank=True):
    return models.ForeignKey(
        blank=blank, null=null, on_delete=on_delete, related_name=related_name, to=settings.AUTH_USER_MODEL)


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0035_consumable_cost_shop_sources"),
        ("events", "0091_event_staff_invite_limits"),
        ("makerspaces", "0136_loan_policy_account_self_renewal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventInductionLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("certification_type", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="induction_links",
                    to="machines.certificationtype")),
                ("created_by", _user()),
                ("event", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="induction_links", to="events.event")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="eventinductionlink",
            constraint=models.UniqueConstraint(fields=("event", "certification_type"), name="induction_link_uniq"),
        ),
        migrations.CreateModel(
            name="GuestCertificationGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("certification_type", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="guest_grants",
                    to="machines.certificationtype")),
                ("granted_by", _user()),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("revoked_by", _user()),
                ("source_event", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="events.event")),
                ("user", _user(null=False, related_name="guest_certification_grants",
                               on_delete=django.db.models.deletion.CASCADE, blank=False)),
            ],
        ),
        migrations.AddIndex(
            model_name="guestcertificationgrant",
            index=models.Index(fields=["makerspace", "user"], name="guestcert_space_user_idx"),
        ),
        migrations.CreateModel(
            name="SupervisedSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.CharField(blank=True, max_length=300)),
                ("opened_at", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", _user()),
                ("event", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="events.event")),
                ("instructor", _user(related_name="supervised_sessions_led", blank=False)),
                ("machine", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="supervised_sessions",
                    to="machines.machine")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
            ],
            options={"ordering": ["-opened_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="supervisedsession",
            index=models.Index(fields=["makerspace", "opened_at"], name="supsession_space_open_idx"),
        ),
        migrations.AddConstraint(
            model_name="supervisedsession",
            constraint=models.UniqueConstraint(
                condition=models.Q(("closed_at__isnull", True)), fields=("machine",),
                name="supervised_session_one_open_per_machine"),
        ),
        migrations.AddConstraint(
            model_name="supervisedsession",
            constraint=models.CheckConstraint(
                condition=models.Q(("closed_at__isnull", True), ("closed_at__gte", models.F("opened_at")), _connector="OR"),
                name="supervised_session_closes_after_open"),
        ),
        migrations.CreateModel(
            name="SupervisedParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField()),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("added_by", _user()),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="participants",
                    to="machines.supervisedsession")),
                ("user", _user(null=False, related_name="supervised_participations",
                               on_delete=django.db.models.deletion.CASCADE, blank=False)),
            ],
        ),
        migrations.AddConstraint(
            model_name="supervisedparticipant",
            constraint=models.UniqueConstraint(fields=("session", "user"), name="supervised_participant_uniq"),
        ),
        migrations.CreateModel(
            name="SupervisedUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("instructor", _user(related_name="supervised_uses_recorded", blank=False)),
                ("session", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="uses",
                    to="machines.supervisedsession")),
                ("user", _user(null=False, related_name="supervised_uses",
                               on_delete=django.db.models.deletion.CASCADE, blank=False)),
            ],
            options={"ordering": ["started_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="superviseduse",
            constraint=models.CheckConstraint(
                condition=models.Q(("ended_at__isnull", True), ("ended_at__gte", models.F("started_at")), _connector="OR"),
                name="supervised_use_ends_after_start"),
        ),
    ]
