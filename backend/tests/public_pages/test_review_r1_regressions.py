"""Stage-4 regressions: quota, retained anchors, bounded cleanup and HTTP shapes."""

from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.backup.event_page_draft_verification import verify_working_draft
from apps.backup.public_page_verification import verify_public_pages
from apps.events.models_website import EventPage, EventPageAsset, EventPageSection
from apps.events.models_website_revisions import EventPageRevision, EventPageRevisionAsset
from apps.events.website_asset_cleanup import collect_unattached
from apps.makerspaces import limits, public_page_assets
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
from apps.makerspaces.public_page_derived import derived_payload
from apps.makerspaces.public_page_projected_serializers import PublicUpcoming
from apps.makerspaces.public_page_contract import empty_document
from apps.makerspaces.public_page_views import PublicPageView
from tests.public_pages.test_l1_assets import picture
from tests.public_pages.test_l1b_speaker_history import speaker_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def test_frontend_regression_payloads_are_exact_serializer_output():
    from apps.makerspaces.public_page_projected_serializers import PublicStats, EventCard
    from apps.makerspaces.public_page_serializers import RevisionMetadata
    path = Path(__file__).parent / "fixtures" / "review-r1.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for key, serializer in (("stats", PublicStats), ("empty_stats", PublicStats),
                            ("event_card", EventCard), ("revision", RevisionMetadata)):
        assert serializer(rows[key]).data == rows[key]


@pytest.mark.parametrize("observed", [None, 123])
def test_recompute_counts_live_maker_assets_once_and_keeps_pending_debt(page_owner, monkeypatch, observed):
    space, actor = page_owner
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda *args: 1_000_000)
    monkeypatch.setattr(public_page_assets.website_assets, "_put", lambda *args: None)
    monkeypatch.setattr(public_page_assets.website_assets, "delete_object", lambda *args: True)
    result = public_page_assets.upload("makerspace", space.pk, actor=actor, version=0,
                                      file=picture(), alt_text="Workbench")
    asset = result["asset"]
    pending_size = 51
    from apps.makerspaces.models_public_pages import MakerspacePublicPage
    page_id = MakerspacePublicPage.objects.get(makerspace=space).pk
    # A live-row receipt must not be counted again; only detached accounted debt is added.
    PublicPageObjectCleanup.objects.create(owner_kind="makerspace", owner_id=space.pk,
        page_id=page_id, object_key=f"pages/makerspaces/{space.pk}/{page_id}/pending.webp",
        size_bytes=pending_size, storage_accounted=True, due_at=timezone.now())
    monkeypatch.setattr("apps.evidence.storage.object_size", lambda key: observed)
    call_command("recompute_storage", space.slug)
    space.refresh_from_db()
    assert space.storage_bytes_used == (observed if observed is not None else asset["size_bytes"]) + pending_size


def test_removed_speaker_anchor_passes_restore_checks_but_real_drift_fails(event_owner):
    from apps.events.services_website import save_content
    from apps.events.website_projection import project
    from apps.backup.build_errors import BackupBuildError
    _, actor, event, page, _, credit = speaker_fixture(event_owner)
    data = project(event)
    data.update(sections=[], sessions=[])
    save_content(event, actor=actor, data=data)
    page.refresh_from_db()
    credit.refresh_from_db()
    assert not credit.section.is_working
    verify_working_draft(page)
    assert verify_public_pages()["event_pages"] == 1
    # Filtering retained anchors must not disable comparison for actual working content.
    page.tagline = "Unsaved drift"
    with pytest.raises(BackupBuildError, match="working website differs"):
        verify_working_draft(page)


def test_cleanup_reaches_orphans_after_fifty_pinned_assets(event_owner, monkeypatch):
    space, _, event = event_owner
    deleted = []
    monkeypatch.setattr("apps.events.website_asset_cleanup.clean_object", deleted.append)
    monkeypatch.setattr("apps.makerspaces.public_page_asset_cleanup.clean_object", deleted.append)
    with transaction.atomic():
        page = EventPage.objects.create(makerspace=space, event=event)
        assets = [EventPageAsset.objects.create(page=page, size_bytes=1, alt_text="Image",
            object_key=f"events/website/{space.pk}/{page.pk}/{index}.webp") for index in range(53)]
        document = {"sections": [], "sessions": [], "section_enabled": {},
                    "editorial_document": empty_document("event")}
        # Retain 50 in history and one in the working graph. Only the old orphan is eligible.
        document["sections"] = [{"slug": f"image-{n}", "asset_id": asset.pk} for n, asset in enumerate(assets[:50])]
        revision = EventPageRevision.objects.create(page=page, source_anchor_start=event.starts_at, document=document)
        EventPageRevisionAsset.objects.bulk_create([EventPageRevisionAsset(revision=revision,
            asset=asset, slot=f"section:image-{n}") for n, asset in enumerate(assets[:50])])
        page.draft_revision = revision
        page.save(update_fields=["draft_revision"])
        EventPageSection.objects.create(page=page, kind="intro", slug="working", asset=assets[50])
    later = timezone.now() + timedelta(hours=25)
    monkeypatch.setattr("apps.events.website_asset_cleanup.timezone.now", lambda: later)
    # A new asset is too young; don't mutate immutable metadata to test its age.
    young = EventPageAsset.objects.create(page=page, size_bytes=1, alt_text="Young",
        object_key=f"events/website/{space.pk}/{page.pk}/young.webp")
    assert collect_unattached(page.pk) == 2
    assert not EventPageAsset.objects.filter(pk__in=[assets[51].pk, assets[52].pk]).exists()
    assert EventPageAsset.objects.filter(page=page).count() == 52
    assert EventPageAsset.objects.filter(pk=young.pk).exists()
    assert deleted and collect_unattached(page.pk) == 0


def test_upcoming_pagination_uses_the_live_page_endpoint(event_owner):
    from apps.makerspaces import public_page_services as pages
    from tests.events.ticketing_helpers import open_event
    space, actor, _ = event_owner
    for _ in range(24):
        open_event(space)
    state = pages.change_handle("makerspace", space.pk, actor=actor, version=0, handle="pagination.lab")
    document = state["document"]
    document["sections"].append({"id": str(uuid4()), "type": "upcoming_events", "enabled": True,
                                "payload": {"title": "Coming up"}})
    state = pages.save("makerspace", space.pk, actor=actor, version=state["version"], document=document)
    pages.publish("makerspace", space.pk, actor=actor, version=state["version"],
                  draft_revision_id=state["draft_revision_id"])
    factory = APIRequestFactory()
    payload = derived_payload("makerspace", space, "upcoming_events", {"title": "Coming up"})
    collection = PublicUpcoming(payload).data
    assert collection["count"] == 25 and len(collection["results"]) == 24
    path = collection["collection_url"]
    response = PublicPageView.as_view()(factory.get(path, {"events_page": 2}), makerspace_slug=space.slug)
    assert response.status_code == 200
    second = next(row["payload"] for row in response.data["sections"] if row["type"] == "upcoming_events")
    assert len(second["results"]) == 1 and second["count"] == 25
    assert second["results"][0] not in collection["results"]
    empty = PublicPageView.as_view()(factory.get(path, {"events_page": "9" * 100}), makerspace_slug=space.slug)
    assert empty.status_code == 200
    assert next(row["payload"] for row in empty.data["sections"] if row["type"] == "upcoming_events")["results"] == []
    for invalid in ("bad", "0", "-1"):
        assert PublicPageView.as_view()(factory.get(path, {"events_page": invalid}),
                                       makerspace_slug=space.slug).status_code == 400
    pages.unpublish("makerspace", space.pk, actor=actor, version=state["version"] + 1)
    assert PublicPageView.as_view()(factory.get(path, {"events_page": 2}),
                                   makerspace_slug=space.slug).status_code == 404
