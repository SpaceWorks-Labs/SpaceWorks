from django.db import migrations, models
import django.db.models.deletion


REVISION_GUARD = """
CREATE FUNCTION events_guard_template_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'certificate template revisions are immutable';
END; $$;
CREATE TRIGGER events_template_revision_immutable BEFORE UPDATE OR DELETE
ON events_eventcertificatetemplaterevision FOR EACH ROW EXECUTE FUNCTION events_guard_template_revision();
CREATE FUNCTION events_guard_artwork() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'certificate artwork is retained'; END IF;
    IF OLD.promoted_at IS NOT NULL OR NEW.promoted_at IS NULL OR
       NEW.event_id IS DISTINCT FROM OLD.event_id OR
       NEW.object_key IS DISTINCT FROM OLD.object_key OR
       NEW.created_at IS DISTINCT FROM OLD.created_at OR
       NEW.size_bytes <= 0 OR NEW.sha256 !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'certificate artwork permits one promotion only';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER events_artwork_immutable BEFORE UPDATE OR DELETE
ON events_eventcertificateartwork FOR EACH ROW EXECUTE FUNCTION events_guard_artwork();
CREATE FUNCTION events_guard_layout_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.template_revision_id IS DISTINCT FROM OLD.template_revision_id OR
       NEW.layout_snapshot IS DISTINCT FROM OLD.layout_snapshot THEN
        RAISE EXCEPTION 'certificate layout snapshot is immutable';
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER events_certificate_layout_immutable BEFORE UPDATE
ON events_eventattendancecertificate FOR EACH ROW EXECUTE FUNCTION events_guard_layout_snapshot();
CREATE FUNCTION events_template_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'events_eventcertificatetemplaterevision' THEN
        IF NEW.artwork_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM events_eventcertificateartwork a
            WHERE a.id = NEW.artwork_id AND a.event_id = NEW.event_id AND a.promoted_at IS NOT NULL
        ) THEN RAISE EXCEPTION 'invalid certificate artwork ownership'; END IF;
    ELSE
        IF NEW.template_revision_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM events_eventcertificatetemplaterevision t
            JOIN events_eventregistration r ON r.event_id = t.event_id
            WHERE t.id = NEW.template_revision_id AND r.id = NEW.registration_id
        ) THEN RAISE EXCEPTION 'invalid certificate template ownership'; END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER events_template_owner BEFORE INSERT ON events_eventcertificatetemplaterevision
FOR EACH ROW EXECUTE FUNCTION events_template_ownership();
CREATE TRIGGER events_certificate_template_owner BEFORE INSERT ON events_eventattendancecertificate
FOR EACH ROW EXECUTE FUNCTION events_template_ownership();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0029_event_broadcasts")]
    operations = [
        migrations.CreateModel(name="EventCertificateArtwork", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("object_key", models.CharField(max_length=512, unique=True)),
            ("size_bytes", models.PositiveBigIntegerField(default=0)),
            ("sha256", models.CharField(max_length=64, blank=True)),
            ("version_id", models.CharField(max_length=1024, blank=True)),
            ("promoted_at", models.DateTimeField(null=True, blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("event", models.ForeignKey(to="events.event", on_delete=django.db.models.deletion.CASCADE,
                                        related_name="certificate_artworks")),
        ]),
        migrations.CreateModel(name="EventCertificateTemplateRevision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("parameters", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("event", models.ForeignKey(to="events.event", on_delete=django.db.models.deletion.CASCADE,
                                        related_name="certificate_template_revisions")),
            ("artwork", models.ForeignKey(to="events.eventcertificateartwork", null=True, blank=True,
                                          on_delete=django.db.models.deletion.PROTECT,
                                          related_name="template_revisions")),
        ], options={"ordering": ("-id",)}),
        migrations.AddField(model_name="eventattendancecertificate", name="template_revision",
                            field=models.ForeignKey(to="events.eventcertificatetemplaterevision",
                                                    on_delete=django.db.models.deletion.PROTECT,
                                                    null=True, blank=True, related_name="certificates")),
        migrations.AddField(model_name="eventattendancecertificate", name="layout_snapshot",
                            field=models.JSONField(default=dict, blank=True)),
        migrations.RunSQL(REVISION_GUARD, """
            DROP FUNCTION events_template_ownership() CASCADE;
            DROP FUNCTION events_guard_layout_snapshot() CASCADE;
            DROP FUNCTION events_guard_artwork() CASCADE;
            DROP FUNCTION events_guard_template_revision() CASCADE;
        """),
    ]
