"""A real historical migration must produce the verifier's canonical draft."""

from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.state import ProjectState
from django.utils import timezone

from tests.account_split.test_p1_data_migration import historical_tables

pytestmark = pytest.mark.django_db(transaction=True)


def test_parallel_session_backfill_matches_canonical_restore_order():
    labels = ["makerspaces.Makerspace", *["events." + name for name in (
        "Event", "EventSeries", "EventPage", "EventSession", "EventPageSection",
        "EventSessionSpeaker", "EventSessionIdentity", "EventSessionAlias", "EventPageRevision",
        "EventPageRevisionAsset", "EventPageRevisionMember", "EventPageAsset")]]
    with historical_tables([("events", "0037_website_revisions")], labels) as old:
        Space = old.get_model("makerspaces", "Makerspace")
        Event = old.get_model("events", "Event")
        Page = old.get_model("events", "EventPage")
        Session = old.get_model("events", "EventSession")
        space = Space.objects.create(name="Backfill order", slug="review-backfill-order")
        start = timezone.now() + timedelta(days=1)
        event = Event.objects.create(makerspace_id=space.pk, title="Parallel programme",
                                     starts_at=start, ends_at=start + timedelta(hours=2))
        page = Page.objects.create(makerspace_id=space.pk, event_id=event.pk)
        for slug in ("z-last", "a-first"):
            Session.objects.create(page_id=page.pk, slug=slug, title=slug, starts_at=start,
                                   ends_at=start + timedelta(minutes=30), visibility="published")
        step = import_module("apps.events.migrations.0038_website_snapshot_backfill")
        step.backfill(old, SimpleNamespace(connection=connection))
        historical = old
        HistoricalPage = historical.get_model("events", "EventPage")
        HistoricalSession = historical.get_model("events", "EventSession")
        draft = HistoricalPage.objects.get(pk=page.pk).draft_revision
        assert [row["slug"] for row in draft.document["sessions"]] == ["a-first", "z-last"]
        assert {str(pk) for pk in HistoricalSession.objects.filter(page_id=page.pk).values_list(
            "identity_id", flat=True)} == {row["session_id"] for row in draft.document["sessions"]}
        # Only the final non-null identity field and is_working field change the
        # shape the independent restore verifier reads; apply those actual operations.
        state = ProjectState.from_apps(old)
        guard = import_module("apps.events.migrations.0039_website_snapshot_guards")
        working = import_module("apps.events.migrations.0040_retained_speaker_sections")
        from django.db.migrations.operations.fields import AlterField
        for operation in [op for op in guard.Migration.operations if isinstance(op, AlterField)] + working.Migration.operations:
            before = state.clone()
            operation.state_forwards("events", state)
            with connection.schema_editor() as editor:
                operation.database_forwards("events", editor, before, state)
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, "events_eventsession")
        assert next(column for column in columns if column.name == "identity_id").null_ok is False
        # Render one coherent historical registry after the deferred field reloads;
        # reverse relations must point to the same revision class as Page's FK.
        state = ProjectState({key: model.clone() for key, model in state.models.items()})
        EventPage = state.apps.get_model("events", "EventPage")
        from apps.backup.event_page_draft_verification import verify_working_draft
        page = EventPage.objects.select_related("draft_revision", "event").get(pk=page.pk)
        RevisionMember = state.apps.get_model("events", "EventPageRevisionMember")
        assert RevisionMember._meta.get_field("revision").remote_field.model is type(page.draft_revision)
        assert list(page.draft_revision.member_references.all()) == []
        assert [row["slug"] for row in page.draft_revision.document["sessions"]] == ["a-first", "z-last"]
        verify_working_draft(page)
