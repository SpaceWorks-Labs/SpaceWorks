"""Keep registration answer documents encrypted in a text envelope."""
from django.db import migrations, models


def refuse_encrypted_reverse(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM events_eventregistration WHERE custom_answers LIKE 'pii:gcm:v1:%' LIMIT 1")
        if cursor.fetchone():
            raise RuntimeError("Decrypt registration documents before restoring JSON storage.")


SQL = r"""
CREATE FUNCTION events_registration_document_fence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint;
BEGIN
  SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id;
  PERFORM pii_assert_mapped_write_allowed(host);
  RETURN NEW;
END; $$;
CREATE TRIGGER events_registration_answers_fence BEFORE INSERT OR UPDATE OF custom_answers
  ON events_eventregistration FOR EACH ROW EXECUTE FUNCTION events_registration_document_fence();
"""
REVERSE_SQL = "DROP TRIGGER events_registration_answers_fence ON events_eventregistration; DROP FUNCTION events_registration_document_fence();"


class Migration(migrations.Migration):
    dependencies = [("events", "0041_g2c_private_assets")]
    operations = [
        migrations.AlterField(model_name="eventregistration", name="custom_answers",
                              field=models.TextField(blank=True, default=None, null=True)),
        migrations.RunSQL(SQL, REVERSE_SQL),
        migrations.RunPython(migrations.RunPython.noop, refuse_encrypted_reverse),
    ]
