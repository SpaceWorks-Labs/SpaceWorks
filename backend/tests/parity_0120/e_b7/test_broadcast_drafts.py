"""E-B7 drafts: private to their author, one open composer draft per author and event, deletable."""
import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from apps.events.models_broadcasts import EventBroadcast
from apps.events.programme.broadcast_draft import delete_draft, own_draft, require_visible, visible_to
from apps.events.programme.commands import ProgrammeConflict
from tests.events.collab_helpers import make_event, make_space, make_staff

pytestmark = pytest.mark.django_db


def draft(event, author, **extra):
    values = {"subject": "Hi", "body": "{}", "statuses": ["registered"], "render_schema_version": 2}
    return EventBroadcast.objects.create(event=event, makerspace=event.makerspace, created_by=author,
                                         **{**values, **extra})


def world():
    space = make_space("drafts-a")
    return make_event(space), make_staff(space, "one"), make_staff(space, "two")


def test_another_authors_draft_is_a_404_but_sent_campaigns_are_shared():
    event, one, two = world()
    mine = draft(event, one)
    sent = draft(event, one, status="sent", render_schema_version=1)
    assert require_visible(mine, one) is mine
    with pytest.raises(NotFound):
        require_visible(mine, two)
    assert require_visible(sent, two) is sent
    rows = EventBroadcast.objects.filter(event=event)
    assert set(visible_to(rows, two)) == {sent}
    assert set(visible_to(rows, one)) == {mine, sent}


def test_one_open_composer_draft_per_author_and_event():
    event, one, two = world()
    first = draft(event, one)
    assert own_draft(event, one) == first and own_draft(event, two) is None
    with pytest.raises(IntegrityError), transaction.atomic():
        draft(event, one)
    draft(event, two)  # another author is unaffected
    draft(event, one, status="sent")  # sent history does not count


def test_delete_removes_only_your_own_draft():
    event, one, two = world()
    mine = draft(event, one)
    with pytest.raises(NotFound):
        delete_draft(mine, two)
    delete_draft(mine, one)
    assert not EventBroadcast.objects.filter(pk=mine.pk).exists()
    sent = draft(event, one, status="sent")
    with pytest.raises(ProgrammeConflict):
        delete_draft(sent, one)
    assert EventBroadcast.objects.filter(pk=sent.pk).exists()
