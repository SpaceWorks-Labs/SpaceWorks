"""G6 tallies (counts only) and X41 server-side draft autosave (versioned)."""
import pytest

from apps.events.programme.broadcast_draft import save_draft
from apps.events.programme.broadcast_tallies import tallies
from apps.events.programme.commands import ProgrammeConflict
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture, queued
from tests.l2_local.helpers import command, composer

pytestmark = pytest.mark.django_db
DRAFT = {"subject": "Edited", "body": "New body {{ name }}", "statuses": ["registered"], "attendance": "any",
         "design": "classic", "ctas": []}


def test_tallies_count_each_recipient_once_and_name_nobody(monkeypatch):
    _space, actor, _member, event, _registration = fixture(monkeypatch)
    campaign, _delivery, _log = queued(event, actor, statuses=["registered"])
    result = tallies(campaign)
    assert result["total"] == 1
    assert sum(result[key] for key in ("delivered", "waiting", "failed", "skipped")) == 1
    response = client_for(actor).get(f"/api/v1/admin/events/{event.pk}/broadcasts/{campaign.pk}/tallies/")
    assert response.status_code == 200
    assert set(response.json()) == {"campaign_id", "status", "total", "delivered", "waiting", "failed", "skipped"}


def test_draft_autosave_bumps_version_and_refuses_a_stale_tab(monkeypatch):
    _space, actor, _member, event, _registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    saved = save_draft(campaign, actor, command(expected_version=campaign.version, draft=DRAFT))
    assert saved.subject == "Edited" and saved.version == campaign.version + 1
    with pytest.raises(ProgrammeConflict):
        save_draft(saved, actor, command(expected_version=campaign.version, draft={**DRAFT, "subject": "Other"}))


def test_draft_patch_route_and_non_drafts_never_change(monkeypatch):
    _space, actor, _member, event, _registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    url = f"/api/v1/admin/events/{event.pk}/broadcasts/{campaign.pk}/"
    body = {"operation_id": "00000000-0000-4000-8000-000000000001", "expected_version": campaign.version,
            "draft": DRAFT}
    response = client_for(actor).patch(url, body, format="json")
    assert response.status_code == 200 and response.json()["subject"] == "Edited"
    type(campaign).objects.filter(pk=campaign.pk).update(status="cancelled")
    body = {**body, "operation_id": "00000000-0000-4000-8000-000000000002",
            "expected_version": campaign.version + 1}
    assert client_for(actor).patch(url, body, format="json").status_code == 409
