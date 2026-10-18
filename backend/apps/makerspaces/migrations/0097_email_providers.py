"""Additive cloud coordination. No host deployment is adopted or enabled."""
import uuid
from django.db import migrations, models
from django.utils import timezone


def backfill(apps, schema_editor):
    Space = apps.get_model("makerspaces", "Makerspace")
    rows = Space.objects.using(schema_editor.connection.alias)
    rows.filter(smtp_host="").update(email_provider="inherit")
    rows.exclude(smtp_host="").update(email_provider="smtp")


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0096_enable_existing_presence")]
    operations = [
        migrations.AddField(model_name='makerspace', name='email_provider', field=models.CharField(max_length=16, blank=True, choices=[
        (v, v) for v in ("", "inherit", "smtp", "resend", "postmark", "ses", "brevo", "mailgun", "sendgrid")
    ])),
        migrations.AddField(model_name='makerspace', name='email_provider_config', field=models.TextField(blank=True)),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
