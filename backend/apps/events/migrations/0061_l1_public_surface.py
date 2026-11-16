"""Release 2 L1: who can find, offline pages, online delivery, short links, embed allow-list."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SHORT_LINK_GUARD = """
CREATE OR REPLACE FUNCTION events_short_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF current_setting('app.allow_immutable_delete', true) = 'on' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'event short links are retired, never deleted';
    END IF;
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.event_id IS DISTINCT FROM OLD.event_id
            OR NEW.makerspace_id IS DISTINCT FROM OLD.makerspace_id OR NEW.code IS DISTINCT FROM OLD.code
            OR NEW.created_at IS DISTINCT FROM OLD.created_at
            OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id AND NEW.created_by_id IS NOT NULL THEN
        RAISE EXCEPTION 'event short link identity is immutable';
    END IF;
    IF OLD.retired_at IS NOT NULL AND (NEW.retired_at IS DISTINCT FROM OLD.retired_at
            OR NEW.retired_by_id IS DISTINCT FROM OLD.retired_by_id AND NEW.retired_by_id IS NOT NULL) THEN
        RAISE EXCEPTION 'a retired event short link cannot change';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM events_event WHERE id = NEW.event_id AND makerspace_id = NEW.makerspace_id) THEN
        RAISE EXCEPTION 'event short link host mismatch';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER events_short_link_guard BEFORE UPDATE OR DELETE ON events_eventshortlink
FOR EACH ROW EXECUTE FUNCTION events_short_link_guard();
CREATE OR REPLACE FUNCTION events_short_link_host() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM events_event WHERE id = NEW.event_id AND makerspace_id = NEW.makerspace_id) THEN
        RAISE EXCEPTION 'event short link host mismatch';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER events_short_link_host BEFORE INSERT ON events_eventshortlink
FOR EACH ROW EXECUTE FUNCTION events_short_link_host();
CREATE TRIGGER events_short_link_visit_host BEFORE INSERT OR UPDATE ON events_eventshortlinkvisitday
FOR EACH ROW EXECUTE FUNCTION events_short_link_host();
"""

SHORT_LINK_GUARD_REVERSE = """
DROP TRIGGER IF EXISTS events_short_link_visit_host ON events_eventshortlinkvisitday;
DROP TRIGGER IF EXISTS events_short_link_host ON events_eventshortlink;
DROP TRIGGER IF EXISTS events_short_link_guard ON events_eventshortlink;
DROP FUNCTION IF EXISTS events_short_link_host();
DROP FUNCTION IF EXISTS events_short_link_guard();
"""

LISTING = [("listed", "Listed"), ("unlisted", "Unlisted")]


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0060_pairwise_judging_guards"),
        ("makerspaces", "0111_fold_modules_and_settings_grants"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="event", name="listing",
            field=models.CharField(choices=LISTING, default="listed", max_length=10),
        ),
        migrations.AddField(
            model_name="event", name="page_state",
            field=models.CharField(choices=[("live", "Live"), ("offline", "Offline")], default="live", max_length=8),
        ),
        migrations.AddField(
            model_name="event", name="delivery_mode",
            field=models.CharField(choices=[("in_person", "In person"), ("online", "Online"), ("hybrid", "Hybrid")],
                                   default="in_person", max_length=10),
        ),
        migrations.AddField(
            model_name="event", name="join_url_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="eventseries", name="listing",
            field=models.CharField(choices=LISTING, default="listed", max_length=10),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(condition=models.Q(("listing__in", ("listed", "unlisted"))),
                                              name="event_listing_valid"),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(condition=models.Q(("page_state__in", ("live", "offline"))),
                                              name="event_page_state_valid"),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(
                condition=models.Q(("delivery_mode__in", ("in_person", "online", "hybrid"))),
                name="event_delivery_mode_valid"),
        ),
        migrations.CreateModel(
            name="EventEmbedPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("allowed_origins", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="event_embed_policy", to="makerspaces.makerspace")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("makerspace_id",)},
        ),
        migrations.CreateModel(
            name="EventShortLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_collation="C", max_length=7, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="short_links",
                                            to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("retired_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("created_at", "id"),
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("retired_at__isnull", True)), fields=("event",),
                                            name="ev_short_link_one_live"),
                    models.CheckConstraint(condition=models.Q(("code__regex", "^[0-9A-Za-z]{7}$")),
                                           name="ev_short_link_code_shape"),
                    models.CheckConstraint(
                        condition=models.Q(("retired_by__isnull", True), ("retired_at__isnull", False), _connector="OR"),
                        name="ev_short_link_retired_by_needs_at"),
                ],
            },
        ),
        migrations.CreateModel(
            name="EventShortLinkVisitDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("day", models.DateField()),
                ("count", models.PositiveIntegerField(default=0)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name="short_link_visit_days", to="events.event")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
            options={
                "ordering": ("day", "id"),
                "constraints": [models.UniqueConstraint(fields=("event", "day"), name="ev_short_link_visit_day_once")],
            },
        ),
        migrations.RunSQL(SHORT_LINK_GUARD, SHORT_LINK_GUARD_REVERSE),
    ]
