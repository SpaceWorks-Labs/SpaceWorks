from django.db import migrations, models
from django.db.models import Count, Max

from apps.inventory.search import SEARCH_CONFIG

TABLE, TRIGGER = "events_event", "event_search_vector_trg"
FUNCTION = f"{TRIGGER}_fn"


def _vector(prefix, with_tags):
    parts = [
        f"setweight(to_tsvector('{SEARCH_CONFIG}', coalesce({prefix}title, '')), 'A')",
        f"setweight(to_tsvector('{SEARCH_CONFIG}', coalesce({prefix}location, '')), 'B')",
    ]
    if with_tags:
        # Tags are a JSON array of short strings; the text form tokenises to one word per tag word.
        parts.append(f"setweight(to_tsvector('{SEARCH_CONFIG}', coalesce({prefix}tags::text, '')), 'C')")
    parts.append(f"setweight(to_tsvector('{SEARCH_CONFIG}', coalesce({prefix}description, '')), 'D')")
    return " || ".join(parts)


def _sql(with_tags):
    return f"""
CREATE OR REPLACE FUNCTION {FUNCTION}() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := {_vector('NEW.', with_tags)};
  RETURN NEW;
END
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS {TRIGGER} ON {TABLE};
CREATE TRIGGER {TRIGGER}
  BEFORE INSERT OR UPDATE ON {TABLE}
  FOR EACH ROW EXECUTE FUNCTION {FUNCTION}();
UPDATE {TABLE} SET search_vector = {_vector('', with_tags)};
"""


def cancel_duplicate_open_drafts(apps, schema_editor):
    """Keep each author's newest composer draft per event; older duplicates become cancelled history."""
    EventBroadcast = apps.get_model("events", "EventBroadcast")
    groups = (EventBroadcast.objects.filter(status="draft", render_schema_version=2, created_by__isnull=False)
              .values("event_id", "created_by_id").annotate(n=Count("pk"), keep=Max("pk")).filter(n__gt=1))
    for group in groups:
        (EventBroadcast.objects.filter(status="draft", render_schema_version=2, event_id=group["event_id"],
                                       created_by_id=group["created_by_id"])
         .exclude(pk=group["keep"]).update(status="cancelled"))


class Migration(migrations.Migration):
    """Parity E-B7: discovery search also reads tags (organiser names are matched by query, since they live
    in another table), and a person keeps at most one open composer draft per event."""

    dependencies = [
        ("events", "0094_series_invites_checkin_lists"),
    ]

    operations = [
        migrations.RunSQL(_sql(True), _sql(False)),
        migrations.RunPython(cancel_duplicate_open_drafts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="eventbroadcast",
            constraint=models.UniqueConstraint(
                fields=("event", "created_by"), condition=models.Q(status="draft", render_schema_version=2),
                name="uniq_event_broadcast_open_draft"),
        ),
    ]
