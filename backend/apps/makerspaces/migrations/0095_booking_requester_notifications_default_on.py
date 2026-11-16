"""Requester booking notifications are ON by default (Phase 2 bookings, owner decision).

New makerspaces get `True` from the field default. Existing makerspaces are flipped only
when the stored `False` is the never-touched original default: a makerspace whose audit
history shows anyone ever saving this setting keeps exactly what they chose. Spaces with a
per-resource override (`BookableSpace.requester_notifications_enabled`) are unaffected,
because the override always wins over the makerspace default.
"""
from django.db import migrations, models

FIELD = "booking_requester_notifications_enabled"


def flip_untouched(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    AuditLog = apps.get_model("audit", "AuditLog")
    db = schema_editor.connection.alias
    touched = AuditLog.objects.using(db).filter(
        action="makerspace.updated", meta__fields__contains=[FIELD],
    ).values("makerspace_id")
    Makerspace.objects.using(db).filter(**{FIELD: False}).exclude(pk__in=touched).update(**{FIELD: True})


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0094_public_profile_contract"),
        ("audit", "0009_audit_verification_runs"),
    ]

    operations = [
        migrations.AlterField(model_name="makerspace", name=FIELD, field=models.BooleanField(default=True)),
        # Irreversible by design: a reverse cannot tell flipped rows from later explicit choices.
        migrations.RunPython(flip_untouched, migrations.RunPython.noop),
    ]
