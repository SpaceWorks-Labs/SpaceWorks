from io import BytesIO
from uuid import uuid4
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import public_page_assets as assets, public_page_services as pages
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
from apps.makerspaces.public_page_asset_cleanup import clean_object
from apps.makerspaces.public_page_errors import PageConflict

pytestmark = pytest.mark.django_db(transaction=True)


def picture():
    data = BytesIO()
    Image.new("RGB", (24, 24), "white").save(data, format="PNG")
    return SimpleUploadedFile("image.png", data.getvalue(), content_type="image/png")


@pytest.fixture
def private_store(monkeypatch):
    objects, freed = {}, []
    monkeypatch.setattr(assets.website_assets, "_put", lambda key, data, mime: objects.update({key: data}))
    monkeypatch.setattr(assets.website_assets, "delete_object", lambda key: objects.pop(key, None) is not False)
    monkeypatch.setattr(assets.limits, "add_storage", lambda owner, size: None)
    monkeypatch.setattr(assets.limits, "free_storage", lambda owner, size: freed.append(size))
    return objects, freed


def test_saved_history_pins_assets_even_after_draft_replacement(page_owner, private_store):
    owner, actor = page_owner
    result = assets.upload("makerspace", owner.pk, actor=actor, version=0, file=picture(), alt_text="Workbench")
    state = result["state"]
    doc = state["document"]
    doc["sections"].append({"id": str(uuid4()), "type": "gallery", "enabled": True,
                            "payload": {"title": "", "items": [{"asset_id": result["asset"]["id"], "caption": ""}]}})
    state = pages.save("makerspace", owner.pk, actor=actor, version=state["version"], document=doc)
    state["document"]["sections"].pop()
    state = pages.save("makerspace", owner.pk, actor=actor, version=state["version"], document=state["document"])
    with pytest.raises(PageConflict):
        assets.delete("makerspace", owner.pk, result["asset"]["id"], actor=actor, version=state["version"])
    assert private_store[0] and not private_store[1]


def test_unattached_delete_commits_before_bytes_and_frees_quota_once(page_owner, private_store):
    owner, actor = page_owner
    result = assets.upload("makerspace", owner.pk, actor=actor, version=0, file=picture(), alt_text="Workbench")
    assets.delete("makerspace", owner.pk, result["asset"]["id"], actor=actor, version=result["state"]["version"])
    assert private_store[0] and not private_store[1]
    job = PublicPageObjectCleanup.objects.get()
    assert clean_object(job.pk)
    assert not private_store[0] and len(private_store[1]) == 1
    assert not clean_object(job.pk)
    assert len(private_store[1]) == 1


def test_failed_storage_keeps_durable_cleanup_and_reserved_version(page_owner, private_store, monkeypatch):
    owner, actor = page_owner
    def unavailable(*args):
        raise StorageUnavailable()
    monkeypatch.setattr(assets.website_assets, "_put", unavailable)
    with pytest.raises(StorageUnavailable):
        assets.upload("makerspace", owner.pk, actor=actor, version=0, file=picture(), alt_text="Workbench")
    assert PublicPageObjectCleanup.objects.filter(completed_at__isnull=True).count() == 1
    state = pages.read_editor("makerspace", owner.pk, actor=actor)
    assert state["version"] == 1 and not state["assets"]
    assert clean_object(PublicPageObjectCleanup.objects.get().pk)


@pytest.mark.parametrize("content", [b"<svg><script>alert(1)</script></svg>", b"not an image"])
def test_malformed_and_svg_bytes_are_rejected_before_reservation(page_owner, content):
    owner, actor = page_owner
    with pytest.raises(ValidationError):
        assets.upload("makerspace", owner.pk, actor=actor, version=0,
                      file=SimpleUploadedFile("file.png", content), alt_text="Description")
    assert not PublicPageObjectCleanup.objects.exists()
