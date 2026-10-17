"""Bind recovery to accounts and retire every session minted before kind-aware auth."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def invalidate_legacy_authentication(apps, schema_editor):
    db = schema_editor.connection.alias
    # Envelopes previously resolved an account by email at drain time. None may
    # acquire a different account when that email is shared after the split.
    apps.get_model("accounts", "PasswordResetEnvelope").objects.using(db).all().delete()
    apps.get_model("sessions", "Session").objects.using(db).all().delete()
    Outstanding = apps.get_model("token_blacklist", "OutstandingToken")
    Blacklisted = apps.get_model("token_blacklist", "BlacklistedToken")
    for token_id in Outstanding.objects.using(db).values_list("pk", flat=True).iterator():
        Blacklisted.objects.using(db).get_or_create(token_id=token_id)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0034_staff_invitation_account"),
        ("sessions", "0001_initial"),
        ("token_blacklist", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(invalidate_legacy_authentication, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="passwordresetenvelope", name="uniq_password_reset_email_ci",
        ),
        migrations.AlterField(
            model_name="passwordresetenvelope", name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="password_reset_envelopes", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="passwordresetenvelope",
            constraint=models.UniqueConstraint(fields=("user",), name="uniq_password_reset_account"),
        ),
    ]
