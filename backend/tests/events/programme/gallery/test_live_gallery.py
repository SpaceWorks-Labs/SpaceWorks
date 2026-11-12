from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.judging.ports import PublicLink, Snapshot
from apps.events.submissions import gallery_projection as gallery


def live(monkeypatch):
    snapshot = Snapshot(id=101, event_id=42, team_id=21, member_ids=(17,), track_ids=(7,), prize_ids=(),
        title="Frozen sensor", description="Public project", content_sha256="a" * 64, eligible=True, current=True,
        metadata_public=True, public_asset_ids=(201,), public_links=(PublicLink(id=211, kind="repo", url="https://github.com/example/project"),),
        expires_at=timezone.now() + timedelta(days=1))
    consent = SimpleNamespace(version=4, metadata_public=True, metadata_generation=1, snapshot_id=101,
        items=Mock())
    item = SimpleNamespace(asset_id=201, link_id=None, generation=1)
    link_choice = SimpleNamespace(asset_id=None, link_id=211, generation=1)
    consent.items.filter.return_value = [item, link_choice]
    entry = SimpleNamespace(pk=1, public_id="11111111-2222-4333-8444-555555555555", event_id=42,
        publication=SimpleNamespace(active=True),
        event=SimpleNamespace(public_token="11111111-2222-4333-8444-555555555550"), snapshot_id=101,
        title="Frozen sensor", description="Public project", metadata_generation=1, hidden_at=None,
        assets=Mock(), links=Mock())
    entry.assets.all.return_value = [SimpleNamespace(asset_id=201, public_id="11111111-2222-4333-8444-555555555557", consent_generation=1)]
    entry.links.all.return_value = [SimpleNamespace(link_id=211, consent_generation=1, url=snapshot.public_links[0].url, kind="repo")]
    ports = Mock()
    ports.snapshot.return_value = snapshot
    ports.public_member_card.return_value = {"handle": "maker-name", "display_name": "Maker", "member_id": 17, "email": "private@example.test"}
    ports.public_asset.return_value = {"state": "ready", "mime": "application/pdf", "bytes": 123, "sha256": "b" * 64,
                                       "kind": "slides", "object_key": "private/key", "filename": "hidden.pdf"}
    model = Mock()
    def first(**filters):
        matches = consent.metadata_public and consent.metadata_generation == filters.get("metadata_generation", 1)
        return Mock(first=Mock(return_value=consent if matches else None))
    model.objects.filter.side_effect = first
    monkeypatch.setattr(gallery, "GalleryConsent", model)
    monkeypatch.setattr(gallery, "runtime", lambda: ports)
    return ports, snapshot, consent, entry, item


def test_public_projection_is_allowlisted_not_a_snapshot_or_asset_dump(monkeypatch):
    _, _, _, entry, _ = live(monkeypatch)
    result = gallery.project_entry(entry)
    assert result["title"] == "Frozen sensor"
    assert result["members"] == [{"display_name": "Maker", "profile_url": "/maker-name"}]
    assert set(result["assets"][0]) == {"public_id", "mime", "bytes", "sha256", "kind", "download_url"}
    assert "member_id" not in repr(result) and "private/key" not in repr(result) and "hidden.pdf" not in repr(result)


@pytest.mark.parametrize("condition", ["withdraw", "hidden", "disqualified", "superseded", "regeneration"])
def test_warm_entry_never_bypasses_live_consent_or_eligibility(monkeypatch, condition):
    ports, snapshot, consent, entry, _ = live(monkeypatch)
    gallery.project_entry(entry)
    if condition == "withdraw":
        consent.metadata_public = False
    elif condition == "hidden":
        entry.hidden_at = timezone.now()
    elif condition == "disqualified":
        ports.snapshot.return_value = replace(snapshot, eligible=False)
    elif condition == "superseded":
        ports.snapshot.return_value = replace(snapshot, current=False)
    else:
        consent.metadata_generation += 1
    with pytest.raises(Http404):
        gallery.project_entry(entry)


def test_regrant_does_not_revive_old_asset_generation(monkeypatch):
    _, _, _, entry, item = live(monkeypatch)
    item.generation = 2
    result = gallery.project_entry(entry)
    assert not result["assets"] and result["links"]


def test_expired_files_keep_the_card_and_hash_without_storage_access(monkeypatch):
    ports, snapshot, _, entry, _ = live(monkeypatch)
    ports.snapshot.return_value = replace(snapshot, expires_at=timezone.now() - timedelta(seconds=1))
    result = gallery.project_entry(entry)
    assert result["files_state"] == "expired" and result["assets"] == result["links"] == []
    assert result["content_sha256"] == snapshot.content_sha256
    ports.public_asset.assert_not_called()


def test_private_profile_has_no_name_or_card_fallback(monkeypatch):
    ports, _, _, entry, _ = live(monkeypatch)
    ports.public_member_card.return_value = None
    assert gallery.project_entry(entry)["members"] == []


def test_completed_gallery_has_a_separate_gate_from_expired_event_website(monkeypatch):
    space = SimpleNamespace(public_site_enabled=True)
    event = SimpleNamespace(pk=42, makerspace=space, is_public=True, status="completed", page_state="live",
                            ends_at=timezone.now() - timedelta(days=100))
    model = Mock()
    model.objects.select_related.return_value.filter.return_value.first.return_value = event
    monkeypatch.setattr(gallery, "Event", model)
    monkeypatch.setattr(gallery, "is_servable", lambda _: True)
    monkeypatch.setattr(gallery, "module_enabled", lambda *args: True)
    monkeypatch.setattr(gallery, "public_surface_available", lambda _: True)
    ports = Mock()
    monkeypatch.setattr(gallery, "runtime", lambda: ports)
    assert gallery.public_event(event_id=42, request_context="trusted-origin") is event
    ports.require_public_origin.assert_called_once_with(event, "trusted-origin")
    space.public_site_enabled = False
    with pytest.raises(Http404):
        gallery.public_event(event_id=42, request_context="trusted-origin")
