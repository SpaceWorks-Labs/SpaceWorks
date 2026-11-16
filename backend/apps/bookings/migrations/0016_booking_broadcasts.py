from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0015_bookablespace_pass_template"),
        ("integrations", "0032_email_source_identity"),
        ("encryption", "0004_pii_write_fence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="BookingBroadcast", fields=[
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
            ("window_start", models.DateTimeField()),
            ("window_end", models.DateTimeField()),
            ("makerspace", models.ForeignKey(to="makerspaces.makerspace", on_delete=django.db.models.deletion.CASCADE)),
            ("space", models.ForeignKey(to="bookings.bookablespace", on_delete=django.db.models.deletion.CASCADE, related_name="broadcasts")),
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL)),
        ], options={"constraints": [models.CheckConstraint(
            condition=models.Q(window_end__gt=models.F("window_start")), name="booking_broadcast_window_order")]}),
        migrations.CreateModel(name="BookingBroadcastDelivery", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(max_length=8, default="pending", choices=[(s, s.title()) for s in ("pending", "sent", "skipped", "failed")])),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("campaign", models.ForeignKey(to="bookings.bookingbroadcast", on_delete=django.db.models.deletion.CASCADE, related_name="deliveries")),
            ("recipient", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("outbox", models.OneToOneField(to="integrations.emaillog", null=True, on_delete=django.db.models.deletion.SET_NULL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("campaign", "recipient"), name="uniq_booking_broadcast_account")]}),
        migrations.RunSQL(
            "CREATE TRIGGER pii_fence_booking_broadcast BEFORE INSERT OR UPDATE OF subject, body "
            "ON bookings_bookingbroadcast FOR EACH ROW EXECUTE FUNCTION pii_fence_email_log()",
            "DROP TRIGGER IF EXISTS pii_fence_booking_broadcast ON bookings_bookingbroadcast",
        ),
    ]
