from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0028_organization_audience"),
        ("integrations", "0032_email_source_identity"),
        ("encryption", "0004_pii_write_fence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="EventBroadcast", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("subject", models.TextField()), ("body", models.TextField()),
            ("status", models.CharField(max_length=10, default="draft", choices=[(s, s.title()) for s in
                ("draft", "queued", "sending", "sent", "cancelled", "failed")])),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("queued_at", models.DateTimeField(null=True)),
            ("completed_at", models.DateTimeField(null=True)),
            ("recipient_cursor", models.PositiveBigIntegerField(default=0)),
            ("recipients_complete", models.BooleanField(default=False)),
            ("statuses", models.JSONField(default=list)),
            ("attendance", models.CharField(max_length=12, default="any", choices=[
                ("any", "Any"), ("attended", "Attended"), ("not_attended", "Not attended")])),
            ("makerspace", models.ForeignKey(to="makerspaces.makerspace", on_delete=django.db.models.deletion.CASCADE)),
            ("event", models.ForeignKey(to="events.event", on_delete=django.db.models.deletion.CASCADE, related_name="broadcasts")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL)),
        ]),
        migrations.CreateModel(name="EventBroadcastDelivery", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(max_length=8, default="pending", choices=[(s, s.title()) for s in ("pending", "sent", "skipped", "failed")])),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("campaign", models.ForeignKey(to="events.eventbroadcast", on_delete=django.db.models.deletion.CASCADE, related_name="deliveries")),
            ("recipient", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("outbox", models.OneToOneField(to="integrations.emaillog", null=True, on_delete=django.db.models.deletion.SET_NULL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("campaign", "recipient"), name="uniq_event_broadcast_account")]}),
        migrations.RunSQL(
            "CREATE TRIGGER pii_fence_event_broadcast BEFORE INSERT OR UPDATE OF subject, body "
            "ON events_eventbroadcast FOR EACH ROW EXECUTE FUNCTION pii_fence_email_log()",
            "DROP TRIGGER IF EXISTS pii_fence_event_broadcast ON events_eventbroadcast",
        ),
    ]
