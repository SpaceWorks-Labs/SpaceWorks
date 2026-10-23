"""Distinct contributor pools, source-bound requirements and role-only consent."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

SQL = r"""
CREATE FUNCTION events_requirement_completion_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.member_id IS NOT DISTINCT FROM OLD.member_id OR NEW.member_id IS NULL)
      AND (NEW.verified_by_id IS NOT DISTINCT FROM OLD.verified_by_id OR NEW.verified_by_id IS NULL)
      AND (to_jsonb(NEW)-ARRAY['member_id','verified_by_id']::text[])=
          (to_jsonb(OLD)-ARRAY['member_id','verified_by_id']::text[]) THEN RETURN NEW; END IF;
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'programme history is append-only'; END IF;
  IF NOT EXISTS(SELECT 1 FROM events_eventroleposting p
      WHERE p.id=NEW.posting_id AND p.event_id=NEW.event_id AND p.makerspace_id=NEW.makerspace_id)
    THEN RAISE EXCEPTION 'requirement completion owner mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_requirement_completion_history BEFORE INSERT OR UPDATE OR DELETE
ON events_eventcontributorrequirementcompletion FOR EACH ROW EXECUTE FUNCTION events_requirement_completion_guard();
CREATE FUNCTION events_role_waiver_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.host_waiver_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM makerspaces_makerspacewaiver w
      WHERE w.id=NEW.host_waiver_id AND w.makerspace_id=NEW.makerspace_id)
    THEN RAISE EXCEPTION 'role waiver owner mismatch'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER events_role_waiver_scope BEFORE INSERT OR UPDATE ON events_eventroleassignment
FOR EACH ROW EXECUTE FUNCTION events_role_waiver_scope_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("events", "0047_gf4_registration_documents"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="eventtickettype", name="purpose", field=models.CharField(
            max_length=16, default="participant", choices=[("participant", "Participant"), ("contributor", "Contributor")])),
        migrations.AddField(model_name="eventtickettype", name="contributor_capacity_policy", field=models.CharField(
            max_length=32, default="event_capacity", choices=[("event_capacity", "Event capacity"),
                ("reserved_contributor_capacity", "Reserved contributor capacity")])),
        migrations.AddConstraint(model_name="eventtickettype", constraint=models.CheckConstraint(
            condition=models.Q(contributor_capacity_policy="event_capacity") | models.Q(purpose="contributor",
                contributor_capacity_policy="reserved_contributor_capacity", capacity__gt=0), name="event_ticket_contributor_pool_shape")),
        migrations.AlterField(model_name="hackathonconfig", name="upload_policy",
            field=models.CharField(default="hackathon-maker-v1", max_length=64)),
        migrations.RunSQL("UPDATE events_hackathonconfig SET upload_policy='hackathon-maker-v1' WHERE upload_policy='maker'",
                          migrations.RunSQL.noop),
        migrations.AddField(model_name="eventroleassignment", name="host_waiver", field=models.ForeignKey(
            "makerspaces.MakerspaceWaiver", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField(model_name="eventroleassignment", name="host_waiver_version_accepted",
            field=models.CharField(max_length=64, blank=True)),
        migrations.AddField(model_name="eventroleassignment", name="host_waiver_accepted_at",
            field=models.DateTimeField(null=True, blank=True)),
        migrations.CreateModel(name="EventContributorRequirementCompletion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("version", models.PositiveIntegerField(default=1)),
            ("kind", models.CharField(max_length=8, choices=[("training", "training"), ("briefing", "briefing")])),
            ("reference_id", models.PositiveIntegerField()), ("requirements_sha256", models.CharField(max_length=64)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("event", models.ForeignKey("events.Event", on_delete=django.db.models.deletion.CASCADE)),
            ("makerspace", models.ForeignKey("makerspaces.Makerspace", on_delete=django.db.models.deletion.CASCADE)),
            ("posting", models.ForeignKey("events.EventRolePosting", on_delete=django.db.models.deletion.CASCADE)),
            ("member", models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="event_requirement_completions")),
            ("verified_by", models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="verified_event_requirement_completions")),
        ], options={"constraints": [models.CheckConstraint(condition=~models.Q(member=models.F("verified_by")),
                                                             name="event_requirement_second_person")]}),
        migrations.RunSQL(SQL, """DROP TRIGGER events_role_waiver_scope ON events_eventroleassignment;
            DROP FUNCTION events_role_waiver_scope_guard();
            DROP TRIGGER events_requirement_completion_history ON events_eventcontributorrequirementcompletion;
            DROP FUNCTION events_requirement_completion_guard();"""),
    ]
