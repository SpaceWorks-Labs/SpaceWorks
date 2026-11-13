from datetime import timedelta
import pytest
from apps.events.models import EventSpeaker
from apps.events.models_website import EventPage
from apps.events.services_website import save_content, set_release
from apps.events.speaker_history import contributions_for
from apps.events.website_projection import project
from tests.events.website_helpers import section, session
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db(transaction=True)


def speaker_fixture(event_owner):
    space, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0,
        "sections": [section("ada", "speaker")],
        "sessions": [session(event, speakers=["ada"], starts_at=event.starts_at + timedelta(minutes=45),
                             ends_at=event.starts_at + timedelta(minutes=60))]})
    page = EventPage.objects.get(event=event)
    set_release(event, actor=actor, released=True, revision=page.revision)
    user = account("credited-speaker")
    credit = EventSpeaker.objects.create(makerspace=space, event=event, user=user,
        display_name="Account speaker", section=page.sections.get(slug="ada"))
    return space, actor, event, page, user, credit


@pytest.mark.parametrize("remove", [False, True])
def test_draft_save_keeps_account_section_and_released_milestone(event_owner, remove):
    space, actor, event, page, user, credit = speaker_fixture(event_owner)
    section_id = credit.section_id
    data = project(event)
    if remove:
        data["sections"], data["sessions"] = [], []
    else:
        data["sections"][0]["title"] = "Pending biography"
        data["sessions"][0]["starts_at"] = event.starts_at
    save_content(event, actor=actor, data=data)
    credit.refresh_from_db()
    assert credit.section_id == section_id
    assert credit.section.is_working is (not remove)
    assert contributions_for(user, space, now=event.starts_at + timedelta(minutes=20)) == []
    row, = contributions_for(user, space, now=event.starts_at + timedelta(minutes=50))
    assert row.event.pk == event.pk and row.role == "speaker"
    assert row.occurred_at == event.starts_at + timedelta(minutes=45)
    if remove:
        assert project(event)["sections"] == []
        assert project(event, public=True)["sections"][0]["slug"] == "ada"


def test_unreleased_and_removed_account_credit_keep_existing_fallback_contract(event_owner):
    space, actor, event, page, user, credit = speaker_fixture(event_owner)
    page.refresh_from_db()
    set_release(event, actor=actor, released=False, revision=page.revision)
    row, = contributions_for(user, space, now=event.starts_at + timedelta(minutes=1))
    assert row.occurred_at == event.starts_at
    credit.removed_at = event.starts_at
    credit.save(update_fields=["removed_at"])
    assert contributions_for(user, space, now=event.ends_at) == []


def test_editorial_names_never_create_account_credit(event_owner):
    space, _, event = event_owner
    user = account("unlinked-speaker")
    assert contributions_for(user, space, now=event.ends_at) == []
