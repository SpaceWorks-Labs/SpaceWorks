"""Additive cloud coordination. No host deployment is adopted or enabled."""
import uuid
from django.db import migrations, models
from django.utils import timezone


def backfill(apps, schema_editor):
    Settings = apps.get_model("integrations", "PlatformEmailSettings")
    Settings.objects.using(schema_editor.connection.alias).exclude(smtp_host="").update(email_provider="smtp")


class Migration(migrations.Migration):
    dependencies = [("integrations", "0039_bd_r2_notification_media")]
    operations = [
        migrations.AddField(model_name='platformemailsettings', name='email_provider', field=models.CharField(max_length=16, blank=True, choices=[
        ("", "Environment / legacy"), ("smtp", "SMTP"), ("resend", "Resend"),
        ("postmark", "Postmark"), ("ses", "Amazon SES"), ("brevo", "Brevo"),
        ("mailgun", "Mailgun"), ("sendgrid", "SendGrid")])),
        migrations.AddField(model_name='platformemailsettings', name='email_provider_config', field=models.TextField(blank=True)),
        migrations.AddField(model_name='emaillog', name='email_retry_at', field=models.DateTimeField(null=True, blank=True, db_index=True)),
        migrations.AddField(model_name='emaillog', name='email_retryable', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='emaillog', name='provider_name', field=models.CharField(max_length=16, blank=True)),
        migrations.AddField(model_name='emaillog', name='provider_message_id', field=models.CharField(max_length=200, blank=True, db_index=True)),
        migrations.AddField(model_name='emaillog', name='provider_recipient_hash', field=models.CharField(max_length=64, blank=True)),
        migrations.AddField(model_name='emaillog', name='provider_delivery_status', field=models.CharField(max_length=16, blank=True)),
        migrations.CreateModel(name='EmailProviderWebhookReceipt', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('makerspace', models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)),
                ('log', models.ForeignKey("integrations.EmailLog", on_delete=models.CASCADE)),
                ('event_key', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ], options={}),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
