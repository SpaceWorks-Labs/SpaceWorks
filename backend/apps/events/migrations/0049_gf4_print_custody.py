from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0048_gf4_contributor_policy")]
    operations = [
        migrations.CreateModel(name="BadgePrintCleanupReceipt", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("makerspace_id_snapshot", models.PositiveBigIntegerField()),
            ("event_id_snapshot", models.PositiveBigIntegerField()),
            ("object_key", models.CharField(max_length=512, unique=True)),
            ("size_bytes", models.PositiveBigIntegerField(default=0)),
            ("released", models.BooleanField(default=False)),
            ("not_before", models.DateTimeField()),
            ("next_attempt_at", models.DateTimeField()),
            ("cleaned_at", models.DateTimeField(blank=True, null=True)),
            ("attempts", models.PositiveIntegerField(default=0)),
            ("lease_token", models.UUIDField(blank=True, null=True)),
            ("lease_until", models.DateTimeField(blank=True, null=True)),
        ]),
        migrations.AddField(model_name="eventpagesection", name="options", field=models.JSONField(blank=True, default=dict)),
        migrations.AlterField(model_name="eventpagesection", name="kind", field=models.CharField(max_length=16, choices=[
            ("intro", "Introduction"), ("logo", "Page logo"), ("speaker", "Speaker"), ("track", "Track"),
            ("room", "Room"), ("sponsor", "Sponsor"), ("faq", "FAQ"), ("resource", "Resource"),
            ("highlight", "Highlight"), ("prizes", "Prizes"), ("judges", "Judges"), ("mentors", "Mentors"),
            ("project_gallery", "Project gallery"), ("results", "Results")])),
        migrations.RunSQL("""
        CREATE FUNCTION sw_print_key_reserved() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM events_badgeprintcleanupreceipt WHERE object_key=NEW.object_key) THEN
            RAISE EXCEPTION 'print key reserved by permanent cleanup custody';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER sw_print_job_key BEFORE INSERT OR UPDATE OF object_key ON events_badgeprintjob
        FOR EACH ROW EXECUTE FUNCTION sw_print_key_reserved();
        CREATE TRIGGER sw_print_resource_key BEFORE INSERT OR UPDATE OF object_key ON events_badgeprintresource
        FOR EACH ROW EXECUTE FUNCTION sw_print_key_reserved();
        CREATE FUNCTION sw_print_custody_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'print cleanup custody is permanent'; END IF;
          IF (NEW.makerspace_id_snapshot, NEW.event_id_snapshot, NEW.object_key, NEW.size_bytes, NEW.not_before)
             IS DISTINCT FROM
             (OLD.makerspace_id_snapshot, OLD.event_id_snapshot, OLD.object_key, OLD.size_bytes, OLD.not_before)
             OR (OLD.released AND NOT NEW.released) THEN
             RAISE EXCEPTION 'print cleanup locator is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER sw_print_custody BEFORE UPDATE OR DELETE ON events_badgeprintcleanupreceipt
        FOR EACH ROW EXECUTE FUNCTION sw_print_custody_guard();
        """, """
        DROP TRIGGER sw_print_job_key ON events_badgeprintjob;
        DROP TRIGGER sw_print_resource_key ON events_badgeprintresource;
        DROP FUNCTION sw_print_key_reserved();
        DROP TRIGGER sw_print_custody ON events_badgeprintcleanupreceipt;
        DROP FUNCTION sw_print_custody_guard();
        """),
    ]
