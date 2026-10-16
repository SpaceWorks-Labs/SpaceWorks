"""Phase 1f-1 tracking; no historical rows are backfilled."""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('integrations', '0032_email_source_identity'), ('makerspaces', '0093_fixed_roles_constraint'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name='SmsSendLog', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)),
            ('purpose', models.CharField(max_length=32, default="authentication")),
            ('provider_source', models.CharField(max_length=8, default="platform", choices=[("platform", "Platform"), ("own", "Own")])),
            ('status', models.CharField(max_length=16, choices=[(s, s.title()) for s in ("sent", "failed", "skipped", "suppressed")])),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={}),
        migrations.CreateModel(name='PushDeliveryAttempt', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('recipient', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+")),
            ('delivery_log', models.ForeignKey("integrations.NotificationDeliveryLog", on_delete=models.CASCADE)),
            ('push_device', models.ForeignKey("integrations.PushDevice", on_delete=models.CASCADE)),
            ('platform', models.CharField(max_length=16, blank=True)),
            ('provider_source', models.CharField(max_length=8, default="platform")),
            ('status', models.CharField(max_length=8, default="pending")),
            ('lease_token', models.UUIDField(null=True, blank=True)),
            ('lease_until', models.DateTimeField(null=True, blank=True)),
            ('attempts', models.PositiveIntegerField(default=0)),
            ('sent_at', models.DateTimeField(null=True, blank=True)),
            ('last_error', models.CharField(max_length=200, blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'constraints': [models.UniqueConstraint(fields=["delivery_log", "push_device"], name="unique_staff_push_attempt")]}),
        migrations.CreateModel(name='EmailProviderEvent', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)),
            ('event_id', models.CharField(max_length=200)),
            ('reason', models.CharField(max_length=16, choices=[("bounce", "Bounce"), ("complaint", "Complaint")])),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'constraints': [models.UniqueConstraint(fields=["makerspace", "event_id"], name="unique_tenant_email_event")]}),
        migrations.AddField(model_name='emaillog', name='provider_source', field=models.CharField(max_length=8, blank=True, choices=[("platform", "Platform"), ("own", "Own")])),
        migrations.AddField(model_name='emaillog', name='provider_message_id', field=models.CharField(max_length=255, blank=True, db_index=True)),
        migrations.AddField(model_name='emaillog', name='bounced_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='emaillog', name='complained_at', field=models.DateTimeField(null=True, blank=True)),
    ]
