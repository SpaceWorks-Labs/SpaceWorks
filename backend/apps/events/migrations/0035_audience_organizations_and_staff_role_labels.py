import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ROLE_LABEL_CHOICES = [("speaker", "Speaker"), ("volunteer", "Volunteer"), ("check_in", "Check-in")]


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0034_website_content_details"),
        ("organizations", "0003_organization_presentation_and_governance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventAudienceOrganization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audience_organizations", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_audiences", to="organizations.organization")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("event", "organization"), name="uniq_event_audience_organization"),
                ],
            },
        ),
        migrations.AddField(
            model_name="eventstaffgrant",
            name="role_label",
            field=models.CharField(blank=True, choices=ROLE_LABEL_CHOICES, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="eventstaffgrantinvite",
            name="role_label",
            field=models.CharField(blank=True, choices=ROLE_LABEL_CHOICES, default="", max_length=16),
        ),
    ]
