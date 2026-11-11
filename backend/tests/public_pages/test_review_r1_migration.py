"""A real historical migration must produce the verifier's canonical draft."""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_parallel_session_backfill_matches_canonical_restore_order():
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    before = [("events", "0037_website_revisions")]
    try:
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        # Only events is rolled back; makerspaces stays at its leaf (0105 dropped a
        # column the events-0037 project state still lists), so use the live model.
        from apps.makerspaces.models import Makerspace as Space
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
        # Inspect the backfill with historical models: is_working is added only
        # in 0040, so current runtime models cannot read this intermediate schema.
        backfilled = [("events", "0038_website_snapshot_backfill")]
        executor = MigrationExecutor(connection)
        executor.migrate(backfilled)
        historical = executor.loader.project_state(backfilled).apps
        HistoricalPage = historical.get_model("events", "EventPage")
        HistoricalSession = historical.get_model("events", "EventSession")
        draft = HistoricalPage.objects.get(pk=page.pk).draft_revision
        assert [row["slug"] for row in draft.document["sessions"]] == ["a-first", "z-last"]
        assert {str(pk) for pk in HistoricalSession.objects.filter(page_id=page.pk).values_list(
            "identity_id", flat=True)} == {row["session_id"] for row in draft.document["sessions"]}
        MigrationExecutor(connection).migrate(leaves)
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, "events_eventsession")
        assert next(column for column in columns if column.name == "identity_id").null_ok is False
        from apps.events.models_website import EventPage
        from apps.backup.event_page_draft_verification import verify_working_draft
        page = EventPage.objects.select_related("draft_revision", "event").get(pk=page.pk)
        assert [row["slug"] for row in page.draft_revision.document["sessions"]] == ["a-first", "z-last"]
        verify_working_draft(page)
    finally:
        # Never leave following tests on a historical schema, including after failure.
        MigrationExecutor(connection).migrate(leaves)
