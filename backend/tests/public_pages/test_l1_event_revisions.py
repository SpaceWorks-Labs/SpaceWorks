from datetime import timedelta
import pytest
from django.db import IntegrityError, transaction, connection
from rest_framework.exceptions import ValidationError
from apps.events.models import Event
from apps.events.models_website import EventPage
from apps.events.services_website import save_content, set_release, set_delay
from apps.events.website_projection import project
from apps.events.website_validation import validate_owner_window
from tests.events.website_helpers import session

pytestmark = pytest.mark.django_db(transaction=True)


def released(event_owner):
    _, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(event)]})
    page = EventPage.objects.get(event=event)
    set_release(event, actor=actor, released=True, revision=page.revision)
    page.refresh_from_db()
    return actor, event, page


def test_publication_survives_draft_removal_and_public_only_delay(event_owner):
    actor, event, page = released(event_owner)
    original = project(event, public=True)["sessions"][0]
    edit = project(event)
    edit["sessions"] = []
    save_content(event, actor=actor, data=edit)
    page.refresh_from_db()
    draft, published = page.draft_revision_id, page.published_revision_id
    assert project(event, public=True)["sessions"][0]["title"] == original["title"]
    set_delay(event, "talk", actor=actor, minutes=20, revision=page.revision, session_id=original["session_id"])
    page.refresh_from_db()
    assert page.draft_revision_id == draft and page.published_revision_id != published
    assert not page.sessions.exists()
    assert project(event, public=True)["sessions"][0]["delay_minutes"] == 20
    assert project(event)["delay_targets"][0]["public_present"]


def test_modern_rename_keeps_identity_and_both_aliases_target_it(event_owner):
    actor, event, page = released(event_owner)
    edit = project(event)
    identity = edit["sessions"][0]["session_id"]
    edit["sessions"][0]["slug"] = "renamed"
    save_content(event, actor=actor, data=edit)
    page.refresh_from_db()
    set_delay(event, "talk", actor=actor, minutes=10, revision=page.revision, session_id=identity)
    assert project(event)["sessions"][0]["slug"] == "renamed"
    assert project(event, public=True)["sessions"][0]["slug"] == "talk"
    assert project(event)["sessions"][0]["delay_minutes"] == 10
    page.refresh_from_db()
    with pytest.raises(ValidationError):
        set_delay(event, "talk", actor=actor, minutes=90, revision=page.revision - 1)


def test_legacy_rename_does_not_carry_delays_or_reassign_old_slug(event_owner):
    actor, event, page = released(event_owner)
    set_delay(event, "talk", actor=actor, minutes=15)
    edit = project(event)
    edit["sessions"][0].pop("session_id")
    edit["sessions"][0]["slug"] = "legacy-new"
    save_content(event, actor=actor, data=edit)
    assert project(event)["sessions"][0]["delay_minutes"] == 0
    assert project(event, public=True)["sessions"][0]["delay_minutes"] == 15
    edit = project(event)
    edit["sessions"][0].pop("session_id")
    edit["sessions"][0]["slug"] = "talk"
    with pytest.raises(ValidationError):
        save_content(event, actor=actor, data=edit)


def test_released_window_survives_working_removal_python_and_sql(event_owner):
    actor, event, page = released(event_owner)
    edit = project(event)
    edit["sessions"] = []
    save_content(event, actor=actor, data=edit)
    event.ends_at = event.starts_at + timedelta(minutes=5)
    from django.core.exceptions import ValidationError as ModelValidationError
    with pytest.raises(ModelValidationError):
        validate_owner_window(event)
    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.filter(pk=event.pk).update(ends_at=event.ends_at)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    event.refresh_from_db()
    page.refresh_from_db()
    set_release(event, actor=actor, released=False, revision=page.revision)
    Event.objects.filter(pk=event.pk).update(ends_at=event.starts_at + timedelta(minutes=5))
