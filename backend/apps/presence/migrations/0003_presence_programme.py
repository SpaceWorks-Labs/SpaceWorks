"""Keep the legacy account alias while adding guest and display semantics."""
from uuid import uuid4

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion


def copy_accounts(apps, schema_editor):
    Session = apps.get_model("presence", "PresenceSession")
    Session.objects.using(schema_editor.connection.alias).update(account_id=models.F("member_id"))


class Migration(migrations.Migration):
    dependencies = [
        ("presence", "0002_claim_session_provenance"),
        ("makerspaces", "0094_public_profile_contract"),
        ("events", "0035_audience_organizations_and_staff_role_labels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField("presencesession", "account", models.ForeignKey(
            settings.AUTH_USER_MODEL, on_delete=deletion.CASCADE, related_name="presence_sessions", null=True)),
        migrations.RunPython(copy_accounts, migrations.RunPython.noop),
        migrations.AlterField("presencesession", "account", models.ForeignKey(
            settings.AUTH_USER_MODEL, on_delete=deletion.CASCADE, related_name="presence_sessions")),
        migrations.AlterField("presencesession", "membership", models.ForeignKey(
            "makerspaces.makerspacemembership", on_delete=deletion.PROTECT, null=True, blank=True)),
        migrations.AddField("presencesession", "status", models.CharField(max_length=24, default="visiting", choices=[
            ("working", "Working"), ("visiting", "Visiting"), ("attending_event", "Attending an event"), ("guest", "Guest")])),
        migrations.AddField("presencesession", "project", models.ForeignKey(
            "makerspaces.memberproject", on_delete=deletion.SET_NULL, null=True, blank=True)),
        migrations.AddField("presencesession", "event_registration", models.OneToOneField(
            "events.eventregistration", on_delete=deletion.SET_NULL, null=True, blank=True, related_name="presence_session")),
        migrations.AddField("presencesession", "hide_on_display", models.BooleanField(default=False)),
        migrations.AddField("presencesession", "revision", models.PositiveIntegerField(default=1)),
        migrations.AddField("presencesession", "expiry_reminded_at", models.DateTimeField(null=True, blank=True)),
        migrations.AlterField("presencesession", "end_reason", models.CharField(max_length=24, blank=True, choices=[
            ("superseded", "Superseded"), ("membership_revoked", "Membership revoked"),
            ("claim_revoked", "Claim revoked"), ("user_ended", "User ended"),
            ("expired", "Expired"), ("staff_ended", "Staff ended")])),
        migrations.AddConstraint("presencesession", models.CheckConstraint(
            condition=models.Q(account=models.F("member")), name="presence_account_matches_member")),
        migrations.AddConstraint("presencesession", models.CheckConstraint(
            condition=models.Q(status__in=["working", "visiting", "attending_event", "guest"]), name="presence_status_valid")),
        migrations.CreateModel("PresenceSettings", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("show_names", models.BooleanField(default=True)),
            ("allow_personal_opt_out", models.BooleanField(default=True)),
            ("display_version", models.UUIDField(default=uuid4, editable=False)),
            ("makerspace", models.OneToOneField("makerspaces.makerspace", on_delete=deletion.CASCADE, related_name="presence_settings")),
        ]),
        migrations.CreateModel("PresencePreference", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("hide_on_display", models.BooleanField(default=False)),
            ("makerspace", models.ForeignKey("makerspaces.makerspace", on_delete=deletion.CASCADE)),
            ("account", models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=deletion.CASCADE)),
        ], options={"constraints": [models.UniqueConstraint(fields=["makerspace", "account"], name="presence_preference_account_space")]}),
    ]
