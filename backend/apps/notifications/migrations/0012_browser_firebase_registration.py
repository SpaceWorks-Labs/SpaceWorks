from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("notifications", "0011_inbox_snooze_browser_alerts"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="BrowserFirebaseInstallation", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("fid_hmac", models.CharField(max_length=64, unique=True)),
        ("owner_epoch", models.UUIDField(default=uuid.uuid4)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
    ]), migrations.CreateModel(name="BrowserFirebaseRegistration", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("project_id", models.CharField(max_length=63)),
        ("fid_ciphertext", models.TextField()),
        ("fid_hmac", models.CharField(max_length=64)),
        ("active", models.BooleanField(default=False)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("confirmed_at", models.DateTimeField(blank=True, null=True)),
        ("revoked_at", models.DateTimeField(blank=True, null=True)),
        ("wake_pending_seq", models.PositiveBigIntegerField(default=0)),
        ("wake_sent_seq", models.PositiveBigIntegerField(default=0)),
        ("wake_retry_at", models.DateTimeField(blank=True, null=True)),
        ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
    ], options={"constraints": [models.UniqueConstraint(fields=("makerspace", "user", "project_id", "fid_hmac"),
                                                          name="uniq_browser_firebase_person_space")]})]
