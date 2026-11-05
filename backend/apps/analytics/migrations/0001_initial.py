"""Release 2 L25 (#163B): the Metabase connection rows. The database roles, schemas,
curated views and provisioning functions are derived objects built by ``analytics.db_sync``
after every migrate (never here), so a hosting that cannot create roles still migrates."""

import django.db.models.deletion
from django.db import migrations, models

import apps.analytics.models


def _fields():
    return [
        ("metabase_url", models.CharField(blank=True, default="", max_length=300)),
        ("embed_secret", models.TextField(blank=True, default="")),
        ("dashboards", models.JSONField(
            blank=True, default=list, validators=[apps.analytics.models.validate_dashboards])),
        ("login_role", models.CharField(blank=True, default="", max_length=63)),
        ("login_password", models.TextField(blank=True, default="")),
        ("login_created_at", models.DateTimeField(blank=True, null=True)),
        ("login_rotated_at", models.DateTimeField(blank=True, null=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("makerspaces", "0127_help_centre_default_on"),
        ("tenant_rls", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyticsConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *_fields(),
                ("show_member_details", models.BooleanField(default=False)),
                ("makerspace", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="analytics_connection",
                    to="makerspaces.makerspace")),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="PlatformAnalyticsConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *_fields(),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
            ],
            options={"abstract": False},
        ),
    ]
