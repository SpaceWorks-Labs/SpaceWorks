"""Parity E-B8: a space's own email display name and Reply-To, and proof its own SMTP account was tested.

Spaces that already send through their own SMTP account are marked verified for their CURRENT settings, so this
release does not silently move their mail to the platform's account. Any later edit to those settings (host, port,
login, password, TLS, From) changes the fingerprint, and the account is unused until a test message passes again.
"""
import hashlib

from django.db import migrations, models


def _fingerprint(space):
    parts = ((space.smtp_host or "").strip().lower(), str(space.smtp_port), space.smtp_username or "",
             space.smtp_password or "", str(bool(space.smtp_use_ssl)), str(bool(space.smtp_use_tls)),
             (space.smtp_from_email or "").strip().lower())
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def grandfather_existing_smtp(apps, schema_editor):
    from django.utils import timezone
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    now = timezone.now()
    rows = Makerspace.objects.exclude(smtp_host="").filter(email_provider__in=("", "smtp"))
    for space in rows.iterator():
        Makerspace.objects.filter(pk=space.pk).update(smtp_verified_fingerprint=_fingerprint(space),
                                                     smtp_verified_at=now)


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0149_request_changes_join_fields")]

    operations = [
        migrations.AddField(model_name="makerspace", name="email_from_name",
                            field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="makerspace", name="email_reply_to",
                            field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="makerspace", name="smtp_verified_fingerprint",
                            field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="makerspace", name="smtp_verified_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(grandfather_existing_smtp, migrations.RunPython.noop),
    ]
