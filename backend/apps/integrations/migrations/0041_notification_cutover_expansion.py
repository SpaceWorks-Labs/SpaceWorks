"""EXPAND checkpoint. Deploy/drain compatible ingress before applying 0042."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.conf import settings


CHANNELS = [("in_app", "Inbox"), ("email", "Email"), ("telegram", "Telegram"), ("slack", "Slack"),
    ("mattermost", "Mattermost"), ("discord", "Discord"), ("webhook", "Signed webhook"),
    ("native_push", "Native push"), ("sms", "SMS"), ("whatsapp", "WhatsApp")]
FEATURES = [(v, label) for v, label in [
    ("hardware_requests", "Hardware requests"), ("printing", "Printing"), ("events", "Events"),
    ("bookings", "Bookings"), ("maintenance", "Maintenance"), ("members", "Members"),
    ("api_access", "API access"), ("devices", "Devices"), ("payments", "Payments"),
    ("stock", "Stock and procurement"), ("certifications", "Certifications"), ("presence", "Presence")]]


def pk():
    return ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"))


def fk(target, **kwargs):
    return models.ForeignKey(to=target, on_delete=django.db.models.deletion.SET_NULL, null=True, **kwargs)


class Migration(migrations.Migration):
    dependencies = [("integrations", "0040_merge_mobile_notifications")]
    operations = [
        migrations.AlterField(model_name="messagingsuppression", name="recipient_kind", field=models.CharField(
            max_length=8, default="phone", choices=[("phone", "Phone"), ("alias", "Provider alias"), ("sender", "Unresolved sender protection")])),
        migrations.AddField(model_name="messagingsenderidentity", name="tenant_reference", field=models.BigIntegerField(null=True)),
        migrations.AlterField(model_name="messagingsenderidentity", name="makerspace",
            field=models.ForeignKey(to="makerspaces.makerspace", null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL)),
        migrations.AddField(model_name="platformwhatsappsettings", name="app_id", field=models.CharField(max_length=64, blank=True)),
        migrations.CreateModel(name="NotificationCutover", fields=[pk(),
            ("route", models.CharField(max_length=16, default="receipt_only", choices=[("receipt_only", "Receipt only"), ("canonical", "Canonical")])),
            ("sending_enabled", models.BooleanField(default=False)),
            ("barrier_at", models.DateTimeField(null=True)),
            ("receipt_watermark", models.BigIntegerField(default=0)),
            ("replay_watermark", models.BigIntegerField(default=0)),
            ("snapshot", models.JSONField(default=dict)),
            ("copied_at", models.DateTimeField(null=True)),
            ("reconciled_at", models.DateTimeField(null=True)),
            ("activated_at", models.DateTimeField(null=True)),
        ], options={"constraints": [models.CheckConstraint(condition=models.Q(pk=1), name="notification_cutover_singleton")]}),
        migrations.CreateModel(name="NotificationIngress", fields=[pk(),
            ("signed_user", fk(settings.AUTH_USER_MODEL)),
            ("configuration", fk("integrations.channelconfiguration")),
            ("makerspace", fk("makerspaces.makerspace")),
            ("makerspace_reference", models.BigIntegerField(null=True)),
            ("configuration_reference", models.BigIntegerField(null=True)),
            ("channel", models.CharField(max_length=16)),
            ("provider", models.CharField(max_length=32)),
            ("transport", models.CharField(max_length=24)),
            ("sender_key", models.CharField(max_length=255)),
            ("generation", models.PositiveIntegerField(default=0)),
            ("credential_version", models.PositiveIntegerField(default=0)),
            ("integration_identity", models.CharField(max_length=255, blank=True)),
            ("dedupe_key", models.CharField(max_length=64, unique=True)),
            ("payload", models.TextField()),
            ("protection_applied", models.BooleanField(default=False)),
            ("state", models.CharField(max_length=16, default="pending", choices=[("pending", "Pending"), ("processed", "Processed"), ("held", "Held")])),
            ("attempts", models.PositiveIntegerField(default=0)),
            ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
            ("last_error", models.CharField(max_length=64, blank=True)),
            ("received_at", models.DateTimeField(auto_now_add=True)),
            ("processed_at", models.DateTimeField(null=True)),
        ], options={"indexes": [models.Index(fields=["next_attempt_at", "id"], condition=~models.Q(state="processed"), name="notification_ingress_due")]}),
        migrations.CreateModel(name="NotificationLegacyMapping", fields=[pk(),
            ("legacy_model", models.CharField(max_length=64)),
            ("legacy_id", models.BigIntegerField()),
            ("canonical_model", models.CharField(max_length=64)),
            ("canonical_id", models.BigIntegerField()),
            ("makerspace", fk("makerspaces.makerspace")),
            ("disposition", models.CharField(max_length=32)),
            ("snapshot", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=["legacy_model", "legacy_id"], name="notification_legacy_mapping")]}),
        migrations.CreateModel(name="NotificationProviderReference", fields=[pk(),
            ("provider", models.CharField(max_length=32)),
            ("sender_key", models.CharField(max_length=255)),
            ("provider_id", models.CharField(max_length=255)),
            ("phone_hash", models.CharField(max_length=64, blank=True)),
            ("delivery_reference", models.BigIntegerField(null=True)),
            ("makerspace_reference", models.BigIntegerField(null=True)),
            ("generation", models.PositiveIntegerField(default=0)),
            ("attempt", models.PositiveSmallIntegerField(default=0)),
            ("ambiguous", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=["provider", "sender_key", "provider_id"], name="notification_provider_reference")]}),
        migrations.CreateModel(name="NotificationCredentialVersion", fields=[pk(),
            ("configuration", fk("integrations.channelconfiguration", related_name="credential_versions")),
            ("configuration_reference", models.BigIntegerField()),
            ("makerspace_reference", models.BigIntegerField()),
            ("generation", models.PositiveIntegerField()),
            ("provider", models.CharField(max_length=32)),
            ("integration_identity", models.CharField(max_length=255)),
            ("sender_key", models.CharField(max_length=255)),
            ("credentials", models.TextField(blank=True)),
            ("retired_at", models.DateTimeField(null=True)),
            ("wiped_at", models.DateTimeField(null=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=["configuration_reference", "generation"], name="notification_credential_generation")]}),
        *[migrations.AddField(model_name="channelconfiguration", name=name, field=field) for name, field in [
            ("use_platform_sender", models.BooleanField(default=False)),
            ("sender_key", models.CharField(max_length=255, blank=True)),
            ("credential_version", models.PositiveIntegerField(default=0)),
            ("activation_hold", models.BooleanField(default=False)),
        ]],
        *[migrations.AddField(model_name="whatsapptemplate", name=name, field=field) for name, field in [
            ("feature", models.CharField(max_length=32, blank=True)),
            ("provider_identity", models.CharField(max_length=255, blank=True)),
            ("validation_schema", models.JSONField(default=dict)),
            ("needs_review", models.BooleanField(default=False)),
        ]],
        migrations.AlterField(model_name="whatsapptemplate", name="configuration", field=models.ForeignKey(
            to="integrations.channelconfiguration", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="templates")),
        migrations.AlterField(model_name="whatsapptemplate", name="template_name", field=models.CharField(max_length=512)),
        migrations.AddConstraint(model_name="whatsapptemplate", constraint=models.UniqueConstraint(
            fields=["provider_identity", "template_name", "locale", "feature", "event", "audience"],
            condition=models.Q(configuration=None), name="uniq_platform_wa_template")),
        *[migrations.AddField(model_name="notificationdelivery", name=name, field=field) for name, field in [
            ("sender_key", models.CharField(max_length=255, blank=True)),
            ("provider_source", models.CharField(max_length=16, blank=True)),
            ("credential_version", models.PositiveIntegerField(default=0)),
            ("recipient_phone_hash", models.CharField(max_length=64, blank=True)),
            ("recipient_alias_hash", models.CharField(max_length=64, blank=True)),
            ("estimated_segments", models.PositiveSmallIntegerField(default=0)),
            ("billed_segments", models.PositiveSmallIntegerField(null=True)),
            ("quota_reserved_at", models.DateTimeField(null=True)),
            ("historical", models.BooleanField(default=False)),
            *[(name, models.DateTimeField(null=True)) for name in ["accepted_at", "sent_at", "delivered_at", "read_at", "failed_at"]],
        ]],
        migrations.AddField(model_name="messagingconsent", name="sender_key", field=models.CharField(max_length=255, blank=True)),
        migrations.AddField(model_name="messagingconsent", name="configuration_generation", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="messagingconsent", name="endpoint", field=models.ForeignKey(to="integrations.notificationendpoint", null=True, on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField(model_name="messagingrecipientcorrelation", name="probe_notification_delivery", field=fk("integrations.notificationdelivery", blank=True)),
        migrations.AlterField(model_name="notificationdelivery", name="state", field=models.CharField(max_length=16, default="retrying",
            choices=[(v, v.title()) for v in ["accepted", "sent", "delivered", "read", "failed", "skipped", "retrying", "held"]])),
        *[migrations.AlterField(model_name=name, name="channel", field=models.CharField(max_length=16, choices=CHANNELS))
          for name in ["channelconfiguration", "notificationdelivery", "notificationpreference"]],
        migrations.AlterField(model_name="notificationdeliverylog", name="channel",
            field=models.CharField(max_length=16, choices=[CHANNELS[-1]] + [v for v in CHANNELS if v[0] not in {"email", "in_app", "whatsapp"}])),
        migrations.AlterField(model_name="dailynotificationcounter", name="channel",
            field=models.CharField(max_length=16, choices=[CHANNELS[-1]] + [v for v in CHANNELS if v[0] not in {"email", "in_app", "whatsapp"}])),
        *[migrations.AlterField(model_name=name, name="feature", field=models.CharField(max_length=32, choices=FEATURES))
          for name in ["notificationpreference", "notificationdeliverylog", "notificationrecipient", "chattemplate"]],
    ]
