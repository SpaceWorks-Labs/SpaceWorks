import django.db.models.deletion
from django.db import migrations, models

import apps.notifications.inbox_scope


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_broadcasts_and_digests"),
        ("integrations", "0032_email_source_identity"),
    ]

    operations = [
        # Adding a non-null field with this default backfills every existing row as staff.
        migrations.AddField(
            model_name="notificationinboxrow", name="audience",
            field=models.CharField(choices=[("staff", "Staff"), ("member", "Member")],
                                   default="staff", max_length=8),
        ),
        migrations.AddField(
            model_name="notificationinboxrow", name="scope",
            field=models.JSONField(blank=True, default=dict,
                                   validators=[apps.notifications.inbox_scope.validate_notification_scope]),
        ),
        migrations.CreateModel(
            name="MemberPushDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"),
                                                   ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")],
                                            default="pending", max_length=8)),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("lease_until", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("inbox_row", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               to="notifications.notificationinboxrow")),
                ("push_device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 to="integrations.pushdevice")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("inbox_row", "push_device"),
                                                        name="uniq_member_push_delivery")],
                "indexes": [models.Index(fields=["status", "lease_until"], name="member_push_recovery_idx")],
            },
        ),
    ]
