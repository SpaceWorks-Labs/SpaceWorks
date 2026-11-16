"""Extend existing rows without changing legacy registration or consent behavior."""
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill(apps, schema_editor):
    alias = schema_editor.connection.alias
    Registration = apps.get_model("events", "EventRegistration")
    from django.db.models import Count
    duplicates = Registration.objects.using(alias).filter(member__isnull=False,
        status__in=("pending_approval", "registered", "waitlisted", "attended")).values(
        "event_id", "member_id").annotate(total=Count("pk")).filter(total__gt=1)
    if duplicates.exists():
        raise RuntimeError("Duplicate active/attended event identities require owner resolution; no rows were merged.")
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            UPDATE events_eventattendancecertificate c
            SET event_id=r.event_id, recipient_member_id=r.member_id,
                event_timezone_name=e.timezone_name
            FROM events_eventregistration r JOIN events_event e ON e.id=r.event_id
            WHERE c.registration_id=r.id
        """)
        cursor.execute("SELECT 1 FROM events_eventattendancecertificate WHERE event_id IS NULL LIMIT 1")
        if cursor.fetchone():
            raise RuntimeError("A legacy certificate has no resolvable event; migration refused.")
        cursor.execute("ALTER TABLE events_eventcertificateartwork DISABLE TRIGGER events_artwork_immutable")
        cursor.execute("UPDATE events_eventcertificateartwork SET resource_id=gen_random_uuid() WHERE resource_id IS NULL")
        cursor.execute("ALTER TABLE events_eventcertificateartwork ENABLE TRIGGER events_artwork_immutable")
    Grant=apps.get_model("events", "EventStaffGrant")
    Entitlement=apps.get_model("events", "EventGrantEntitlement")
    for grant in Grant.objects.using(alias).order_by("pk").iterator(chunk_size=500):
        Entitlement.objects.using(alias).create(grant_id=grant.pk, makerspace_id=grant.makerspace_id,
            event_id=grant.event_id, series_id=grant.series_id, source_kind="manual",
            permissions=grant.permissions, created_by_id=grant.granted_by_id,
            revoked_at=grant.revoked_at, revoked_by_id=grant.revoked_by_id)


def reverse_certificate_guard(apps, schema_editor):
    Certificate=apps.get_model("events", "EventAttendanceCertificate")
    if Certificate.objects.using(schema_editor.connection.alias).filter(
        models.Q(registration__isnull=True) | models.Q(response__isnull=True) | ~models.Q(kind="attendance")
    ).exists():
        raise RuntimeError("Programme certificates exist; reversal would discard their typed subjects.")
    if apps.get_model("events", "EventBroadcast").objects.using(schema_editor.connection.alias).filter(status="scheduled").exists():
        raise RuntimeError("Scheduled broadcasts must be cancelled before reverting the programme schema.")


def reverse_backfill(apps, schema_editor):
    apps.get_model("events", "EventGrantEntitlement").objects.using(
        schema_editor.connection.alias).filter(source_kind="manual").delete()


class Migration(migrations.Migration):
    dependencies = [("events", "0042_events_programme_schema")]
    operations = [
        migrations.AlterField(model_name="eventbroadcast", name="status", field=models.CharField(max_length=10, default="draft", choices=[(s, s.title()) for s in ("draft", "scheduled", "queued", "sending", "sent", "cancelled", "failed")])),
        migrations.AddField(model_name='event', name='version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='event', name='event_date_revision', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='eventregistration', name='version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='eventregistration', name='answer_locked_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='eventregistration', name='date_review_required', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='eventregistration', name='credential_mode', field=models.CharField(max_length=8, default='legacy', choices=(('legacy', 'Legacy'), ('v2', 'Version 2'), ('inert', 'Inert')))),
        migrations.AddField(model_name='eventattendancecertificate', name='event', field=models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='certificates', null=True)),
        migrations.AddField(model_name='eventattendancecertificate', name='recipient_member', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_certificates')),
        migrations.AddField(model_name='eventattendancecertificate', name='role_assignment', field=models.ForeignKey('events.EventRoleAssignment', on_delete=models.PROTECT, null=True, blank=True, related_name='certificates')),
        migrations.AddField(model_name='eventattendancecertificate', name='kind', field=models.CharField(max_length=24, choices=[('attendance', 'Attendance'), ('participant', 'Participant'), ('finalist', 'Finalist'), ('winner', 'Winner'), ('volunteer_thanks', 'Volunteer thanks'), ('mentor_thanks', 'Mentor thanks'), ('judge_thanks', 'Judge thanks')], default='attendance')),
        migrations.AddField(model_name='eventattendancecertificate', name='award', field=models.ForeignKey('events.HackathonPrize', on_delete=models.PROTECT, null=True, blank=True, related_name='certificates')),
        migrations.AddField(model_name='eventattendancecertificate', name='result_revision', field=models.ForeignKey('events.EventResultRevision', on_delete=models.PROTECT, null=True, blank=True, related_name='certificates')),
        migrations.AddField(model_name='eventattendancecertificate', name='public_verification_enabled', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='eventattendancecertificate', name='event_timezone_name', field=models.CharField(max_length=64, default='UTC')),
        migrations.AddField(model_name='eventattendancecertificate', name='render_token', field=models.UUIDField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='eventattendancecertificate', name='render_started_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='eventattendancecertificate', name='render_attempts', field=models.PositiveIntegerField(default=0, editable=False)),
        migrations.AddField(model_name='eventbroadcast', name='version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='eventbroadcast', name='render_schema_version', field=models.PositiveSmallIntegerField(default=1, choices=[(1, 'Legacy'), (2, 'Composer')])),
        migrations.AddField(model_name='eventbroadcast', name='design', field=models.CharField(max_length=12, default='classic', choices=[(name, name.title()) for name in ('classic', 'bold', 'minimal')])),
        migrations.AddField(model_name='eventbroadcast', name='available_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='eventbroadcast', name='confirmed_preview', field=models.ForeignKey('events.EventBroadcastPreview', null=True, blank=True, on_delete=models.RESTRICT, related_name='confirmed_campaigns')),
        migrations.AddField(model_name='eventcertificateartwork', name='resource_id', field=models.UUIDField(null=True, editable=False)),
        migrations.RunPython(backfill, reverse_backfill),
        migrations.AlterField(model_name='eventattendancecertificate', name='event', field=models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='certificates')),
        migrations.AlterField(model_name='eventcertificateartwork', name='resource_id', field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
        migrations.AlterField(model_name="eventattendancecertificate", name='registration', field=models.ForeignKey('events.EventRegistration', on_delete=models.PROTECT, related_name='attendance_certificates', null=True, blank=True)),
        migrations.AlterField(model_name="eventattendancecertificate", name='response', field=models.ForeignKey('events.EventFeedbackResponse', on_delete=models.PROTECT, related_name='certificates', null=True, blank=True)),
        migrations.RemoveConstraint(model_name="eventattendancecertificate", name='uniq_event_certificate_revision'),
        migrations.RemoveConstraint(model_name="eventattendancecertificate", name='uniq_live_event_certificate'),
        migrations.AddConstraint(model_name='eventattendancecertificate', constraint=models.CheckConstraint(condition=models.Q(registration__isnull=False, role_assignment__isnull=True) | models.Q(registration__isnull=True, role_assignment__isnull=False, response__isnull=True), name='event_certificate_exact_subject')),
        migrations.AddConstraint(model_name='eventattendancecertificate', constraint=models.UniqueConstraint(fields=['registration', 'kind', 'award', 'revision'], condition=models.Q(registration__isnull=False), nulls_distinct=False, name='event_cert_reg_revision_v2')),
        migrations.AddConstraint(model_name='eventattendancecertificate', constraint=models.UniqueConstraint(fields=['role_assignment', 'kind', 'award', 'revision'], condition=models.Q(role_assignment__isnull=False), nulls_distinct=False, name='event_cert_role_revision_v2')),
        migrations.AddConstraint(model_name='eventattendancecertificate', constraint=models.UniqueConstraint(fields=['registration', 'kind', 'award'], condition=models.Q(registration__isnull=False) & ~models.Q(status='revoked'), nulls_distinct=False, name='event_cert_reg_live_v2')),
        migrations.AddConstraint(model_name='eventattendancecertificate', constraint=models.UniqueConstraint(fields=['role_assignment', 'kind', 'award'], condition=models.Q(role_assignment__isnull=False) & ~models.Q(status='revoked'), nulls_distinct=False, name='event_cert_role_live_v2')),
        migrations.AddConstraint(model_name='eventbroadcast', constraint=models.CheckConstraint(condition=models.Q(render_schema_version__in=[1, 2]), name='event_broadcast_known_schema')),
        migrations.AddConstraint(model_name='eventbroadcast', constraint=models.CheckConstraint(condition=~models.Q(status='scheduled') | models.Q(render_schema_version=2, available_at__isnull=False, confirmed_preview__isnull=False), name='event_broadcast_scheduled_proof')),
        migrations.AddIndex(model_name='eventbroadcast', index=models.Index(fields=['status', 'available_at'], name='event_broadcast_due_idx')),
        migrations.AlterModelOptions(name="eventattendancecertificate", options={"ordering": ["event_id", "id"]}),
        migrations.RemoveConstraint(model_name="eventregistration", name="uniq_active_event_registration_member"),
        migrations.AddConstraint(model_name="eventregistration", constraint=models.UniqueConstraint(
            fields=("event", "member"), condition=models.Q(member__isnull=False,
                status__in=("pending_approval", "registered", "waitlisted", "attended")),
            name="uniq_active_event_registration_member")),
        # This is reversed first, before old non-null/uniqueness constraints return.
        migrations.RunPython(migrations.RunPython.noop, reverse_certificate_guard),
    ]
