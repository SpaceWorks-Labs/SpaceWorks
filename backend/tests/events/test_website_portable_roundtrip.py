from tests.events.website_helpers import make_page, make_session
"""Drive real portable row materialization and its private-object promotion journal."""

import hashlib
import json
from pathlib import Path

import pytest

from apps.events.models import Event
from apps.events.models_website import (
    EventPage, EventPageAsset, EventPageSection, EventSession, EventSessionSpeaker,
)
from apps.makerspaces.models import Makerspace
from apps.makerspaces.website_assets import owns
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration.object_export import object_member_path
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import memory_objects  # noqa: F401 -- fixture
from tests.events.website_parity_helpers import metadata, profile
from tests.events.website_helpers import snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def test_website_content_and_private_bytes_roundtrip_with_release_and_origins_reset(memory_objects):
    data = b"verified private website bytes"
    def website(space, user, request):
        space.website_embed_origins = ["https://old-partner.example"]
        space.save(update_fields=["website_embed_origins"])
        event = Event.objects.get(makerspace=space, title="Portable workshop")
        page = make_page(makerspace=space, event=event, released=True, **metadata())
        key = f"events/website/{space.pk}/{page.pk}/image.webp"
        asset = EventPageAsset.objects.create(page=page, object_key=key, size_bytes=len(data), alt_text="Portrait")
        speaker = EventPageSection.objects.create(page=page, kind="speaker", slug="speaker", title="Speaker",
                                                 asset=asset, visibility="published", **profile())
        EventPageSection.objects.create(page=page, kind="sponsor", slug="lab", title="Lab", asset=asset,
                                         visibility="published", sponsor_tier="gold")
        EventPageSection.objects.create(page=page, kind="highlight", slug="workshops", title="Workshops",
                                         visibility="published", icon="wrench", body="Hands-on learning.")
        session = make_session(page=page, slug="talk", title="Talk", starts_at=event.starts_at, ends_at=event.ends_at, visibility="published")
        EventSessionSpeaker.objects.create(session=session, speaker=speaker)
        snapshot(page)
        memory_objects["private"][key] = data  # Force target collision with the source footprint.
        return key

    with enabled_encryption():
        source = make_space("website-roundtrip")
        user = make_user("website-roundtrip")
        with portable_import_case(source, user, prepare_source=website) as case:
            case.decide_walk_in(user)
            key = case.source_data
            member = Path(case.root) / object_member_path("private", key)
            member.parent.mkdir(parents=True, exist_ok=True); member.write_bytes(data)
            manifest = Path(case.root) / "objects/manifest.jsonl"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps({"bucket_kind": "private", "source_key": key,
                "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "version_id": "source-version", "content_type": "image/webp"}) + "\n")
            result = materialize_tenant(case.root, case.job, case.carried,
                target_identity={"slug": "website-roundtrip-target"})
    target = Makerspace.objects.get(pk=result.target_makerspace_id)
    page = EventPage.objects.get(makerspace=target)
    asset = page.assets.get()
    assert not page.released and target.website_embed_origins == []
    speaker = page.sections.get(kind="speaker")
    assert speaker.asset_id == asset.pk and page.sessions.get().slug == "talk"
    assert page.sessions.get().speaker_links.get().speaker_id == speaker.pk
    assert all(getattr(page, key) == value for key, value in metadata().items())
    assert all(getattr(speaker, key) == value for key, value in profile().items())
    assert page.sections.get(kind="sponsor").sponsor_tier == "gold"
    assert page.sections.get(kind="sponsor").asset_id == asset.pk
    assert page.sections.get(kind="highlight").icon == "wrench"
    assert asset.object_key != key
    assert memory_objects["private"][asset.object_key] == data
    assert owns(asset.object_key, "events", target.pk, page.pk, asset=asset)
