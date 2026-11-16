import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0008_invitation_email_digest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="review_status",
            field=models.CharField(
                choices=[
                    ("pending_review", "Pending review"),
                    ("changes_requested", "Changes requested"),
                    ("approved", "Approved"),
                    ("declined", "Declined"),
                    ("suspended", "Suspended"),
                ],
                db_index=True, default="approved", max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="OrganizationReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(
                    choices=[
                        ("submitted", "Submitted"), ("changes_requested", "Changes requested"),
                        ("approved", "Approved"), ("declined", "Declined"),
                        ("suspended", "Suspended"), ("reactivated", "Reactivated"),
                    ],
                    max_length=24,
                )),
                ("reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="reviews",
                    to="organizations.organization",
                )),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [models.Index(
                    fields=["organization", "action", "created_at"], name="org_review_history_idx",
                )],
            },
        ),
    ]
