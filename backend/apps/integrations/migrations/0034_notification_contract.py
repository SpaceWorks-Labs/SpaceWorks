# Notification contract schema; runtime drift checked by makemigrations --check.
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrations', '0033_notification_endpoints'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    operations = [
        migrations.CreateModel(
            name='NotificationEnvelope',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('makerspace', models.ForeignKey('makerspaces.Makerspace', on_delete=models.CASCADE)),
                ('feature', models.CharField(max_length=32)),
                ('stream', models.CharField(max_length=32, blank=True)),
                ('event', models.CharField(max_length=64)),
                ('audience', models.CharField(max_length=16, choices=[(v, v) for v in ('staff', 'requester', 'member')])),
                ('recipient', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
                ('subject_type', models.ForeignKey('contenttypes.ContentType', null=True, on_delete=models.SET_NULL)),
                ('subject_id', models.CharField(max_length=64, blank=True)),
                ('scope', models.JSONField(default=dict)),
                ('context', models.JSONField(default=dict)),
                ('routing_snapshot', models.JSONField(default=dict)),
                ('message_body', models.TextField(blank=True)),
                ('source_kind', models.CharField(max_length=64)),
                ('source_id', models.CharField(max_length=64, blank=True)),
                ('revision', models.CharField(max_length=64, default='1')),
                ('dedup_key', models.CharField(max_length=200, unique=True)),
                ('timing_policy', models.CharField(max_length=16, default='immediate', choices=[(v, v) for v in ('immediate', 'deferred', 'digest')])),
                ('mandatory', models.BooleanField(default=False)),
                ('available_at', models.DateTimeField(null=True)),
                ('processed_at', models.DateTimeField(null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [models.Index(fields=['processed_at', 'available_at'], name='envelope_due_idx')],
            },
        ),
        migrations.CreateModel(
            name='NotificationDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('makerspace', models.ForeignKey('makerspaces.Makerspace', on_delete=models.CASCADE)),
                ('envelope', models.ForeignKey('integrations.NotificationEnvelope', on_delete=models.CASCADE, related_name='deliveries')),
                ('channel', models.CharField(max_length=16, choices=[('in_app', 'Inbox'), ('email', 'Email'), ('telegram', 'Telegram'), ('slack', 'Slack'), ('mattermost', 'Mattermost'), ('discord', 'Discord'), ('webhook', 'Signed webhook'), ('native_push', 'Native push'), ('whatsapp', 'WhatsApp')])),
                ('endpoint', models.ForeignKey('integrations.NotificationEndpoint', null=True, on_delete=models.SET_NULL)),
                ('target_key', models.CharField(max_length=80)),
                ('provider', models.CharField(max_length=32)),
                ('integration_generation', models.PositiveIntegerField(default=0)),
                ('integration_identity', models.CharField(max_length=255, blank=True)),
                ('state', models.CharField(max_length=16, choices=[('accepted', 'Accepted'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed'), ('skipped', 'Skipped'), ('retrying', 'Retrying')], default='retrying')),
                ('provider_id', models.CharField(max_length=255, blank=True)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('ambiguous_count', models.PositiveSmallIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(null=True)),
                ('last_error', models.CharField(max_length=100, blank=True)),
                ('retryable', models.BooleanField(default=False)),
                ('claim_until', models.DateTimeField(null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=['envelope', 'channel', 'target_key'], name='uniq_envelope_delivery'), models.UniqueConstraint(fields=['envelope', 'channel'], name='uniq_envelope_channel')],
                'indexes': [models.Index(fields=['state', 'next_attempt_at'], name='delivery_due_idx')],
            },
        ),
    ]
