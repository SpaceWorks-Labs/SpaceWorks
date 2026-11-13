"""Global account-level member profile (decisions 302-305): schema.

Additive. Creates the four account-level tables and relaxes the member-owned branch of the two
handle constraints so a handle no longer needs a legacy per-membership profile: a post-0.12
account owns a handle whose `profile` pointer is NULL. Existing rows satisfy the relaxed check
(they are a strict subset of it), so nothing is rewritten here; the data merge is 0153.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

STATUS = [
    ("student", "Student"), ("working", "Working"), ("freelancing", "Freelancing"),
    ("looking_for_work", "Looking for work"), ("open_to_collaborate", "Open to collaborate"),
    ("building_startup", "Building a startup"), ("other", "Other"),
]


def _owner_check(name):
    return models.CheckConstraint(condition=(
        models.Q(user__isnull=False, makerspace__isnull=True, organization__isnull=True)
        | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=False, organization__isnull=True)
        | models.Q(user__isnull=True, profile__isnull=True, makerspace__isnull=True, organization__isnull=False)
    ), name=name)


def _toggle():
    return models.BooleanField(default=True)


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0151_events_badge_switches_on"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_visible", models.BooleanField(default=True, help_text="Whether signed-in users can see this profile.")),
                ("public_visible", models.BooleanField(default=False)),
                ("public_consented_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("show_status", _toggle()), ("show_about", _toggle()), ("show_experience", _toggle()),
                ("show_education", _toggle()), ("show_achievements", _toggle()), ("show_projects", _toggle()),
                ("show_skills", _toggle()), ("show_links", _toggle()), ("show_interests", _toggle()),
                ("show_events", _toggle()), ("show_spaces", _toggle()), ("show_certifications", _toggle()),
                ("show_activity_graph", models.BooleanField(default=True)),
                ("show_speaking", models.BooleanField(default=False)),
                ("show_machine_activity", models.BooleanField(default=False)),
                ("show_bookings", models.BooleanField(default=False)),
                ("show_loans", models.BooleanField(default=False)),
                ("headline", models.CharField(blank=True, default="", max_length=200)),
                ("status", models.CharField(blank=True, choices=STATUS, default="", max_length=24)),
                ("status_note", models.CharField(blank=True, default="", max_length=120)),
                ("institution", models.CharField(blank=True, default="", max_length=200)),
                ("bio", models.TextField(blank=True, default="")),
                ("avatar_key", models.CharField(blank=True, default="", max_length=500)),
                ("domains", models.JSONField(blank=True, default=list)),
                ("skills", models.JSONField(blank=True, default=list)),
                ("links", models.JSONField(blank=True, default=list)),
                ("interests", models.JSONField(blank=True, default=list)),
                ("languages", models.JSONField(blank=True, default=list)),
                ("education", models.JSONField(blank=True, default=list)),
                ("github_username", models.CharField(blank=True, default="", max_length=39)),
                ("github_contributions", models.PositiveIntegerField(blank=True, null=True)),
                ("github_synced_at", models.DateTimeField(blank=True, null=True)),
                ("merged_from_legacy", models.BooleanField(default=False, editable=False)),
                ("open_notice_pending", models.BooleanField(default=False, editable=False)),
                ("public_reconfirm_pending", models.BooleanField(default=False, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="account_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["open_notice_pending"], name="acctprofile_notice_idx")]},
        ),
        migrations.CreateModel(
            name="AccountProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("subtitle", models.CharField(blank=True, default="", max_length=200)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("public_visible", models.BooleanField(default=True)),
                ("description", models.TextField(blank=True, default="")),
                ("image_key", models.CharField(blank=True, default="", max_length=500)),
                ("links", models.JSONField(blank=True, default=list)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("source_submission_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="projects", to="makerspaces.accountprofile")),
            ],
            options={"ordering": ("position", "id")},
        ),
        migrations.AddConstraint("accountproject", models.UniqueConstraint(
            fields=("profile", "source_submission_id"), name="account_project_one_import_per_submission")),
        migrations.CreateModel(
            name="AccountTimelineEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("experience", "Experience"), ("education", "Education"),
                                                   ("volunteering", "Volunteering")], max_length=16)),
                ("title", models.CharField(max_length=200)),
                ("organization", models.CharField(blank=True, default="", max_length=200)),
                ("location", models.CharField(blank=True, default="", max_length=200)),
                ("start", models.DateField()),
                ("end", models.DateField(blank=True, null=True)),
                ("description", models.TextField(blank=True, default="")),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="timeline", to="makerspaces.accountprofile")),
            ],
            options={"ordering": ("order", "-start", "id")},
        ),
        migrations.AddConstraint("accounttimelineentry", models.CheckConstraint(
            condition=models.Q(end__isnull=True) | models.Q(end__gte=models.F("start")),
            name="account_timeline_date_order")),
        migrations.CreateModel(
            name="ProfileAchievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("issuer", models.CharField(blank=True, default="", max_length=160)),
                ("achieved_on", models.DateField(blank=True, null=True)),
                ("url", models.URLField(blank=True, default="", max_length=500)),
                ("description", models.TextField(blank=True, default="", max_length=2000)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="achievements", to="makerspaces.accountprofile")),
            ],
            options={"ordering": ("order", "-achieved_on", "id")},
        ),
        migrations.AlterField("publichandle", "profile", models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
            related_name="handles", to="makerspaces.memberprofile")),
        migrations.AlterField("publichandleredirect", "profile", models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
            related_name="handle_redirects", to="makerspaces.memberprofile")),
        migrations.RemoveConstraint("publichandle", "public_handle_typed_owner"),
        migrations.AddConstraint("publichandle", _owner_check("public_handle_typed_owner")),
        migrations.RemoveConstraint("publichandleredirect", "redirect_handle_typed_owner"),
        migrations.AddConstraint("publichandleredirect", _owner_check("redirect_handle_typed_owner")),
    ]
