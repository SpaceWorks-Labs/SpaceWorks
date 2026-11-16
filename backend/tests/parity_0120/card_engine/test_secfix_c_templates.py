"""SECURITY-REVIEW M9, M12 and L-M2 for Card Studio templates.

M9: applying a SAVED space template needs the template authority itself, not just edit rights on one design (an
event co-organiser can edit their event card but must not walk the space's member and staff card templates).
M12: a template import validates everything and charges storage BEFORE any byte is written, and a failure part way
deletes what it wrote, so a refused import leaves nothing in the bucket. L-M2: template quotas lock the space row.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import NotFound, ValidationError

from apps.card_designs import resolution, templates, templates_files
from apps.card_designs.models import CardDesign, CardDesignAsset, CardTemplate
from tests.l3_local.helpers import card_space, manager, member
from tests.open_items_0120.test_platform_credential_limits import _limit

from .conftest import document, layer, png

pytestmark = pytest.mark.django_db


def _design(space, actor, doc=None):
    row, _created = resolution.get_or_create(space, "member_cards", actor=actor)
    if doc is not None:
        CardDesign.objects.filter(pk=row.pk).update(document=doc)
        row.refresh_from_db()
    return row


@pytest.fixture
def bucket(store, monkeypatch):
    monkeypatch.setattr(templates_files, "delete_quietly", lambda key: store.pop(key, None))
    return store


# --- M9 ---------------------------------------------------------------------------------------------------------

def test_a_saved_template_is_refused_to_someone_without_template_authority():
    space = card_space("m9-refused")
    owner = manager(space)
    design = _design(space, owner)
    saved = templates.create_from_design(owner, space, design, "Staff card master")
    outsider, _membership = member(space, "m9-outsider")
    revision = design.revision
    with pytest.raises(NotFound):
        templates.apply(outsider, space, design, saved.pk, expected_revision=revision)
    design.refresh_from_db()
    assert design.revision == revision                                   # nothing was copied in


def test_the_template_authority_still_applies_a_saved_template():
    space = card_space("m9-allowed")
    owner = manager(space)
    design = _design(space, owner)
    saved = templates.create_from_design(owner, space, design, "Mine")
    applied, _unplaced = templates.apply(owner, space, design, saved.pk, expected_revision=design.revision)
    assert applied.pk == design.pk


def test_a_built_in_template_needs_no_template_authority():
    space = card_space("m9-builtin")
    owner = manager(space)
    design = _design(space, owner)
    outsider, _membership = member(space, "m9-builtin-member")
    applied, _ = templates.apply(outsider, space, design, "builtin:aurora:light",
                                 expected_revision=design.revision, keep_fields=False)
    assert applied.pk == design.pk


# --- M12 --------------------------------------------------------------------------------------------------------

def _exported(space, owner):
    asset_id = templates_files._create_asset(owner, space, "image", png((30, 30)))
    design = _design(space, owner, document([layer("image", 5, 5, 20, 20, asset_id=asset_id, fit="cover")]))
    row = templates.create_from_design(owner, space, design, "With image")
    return templates_files.export_file(space, row)


def _refused_cleanly(bucket, target, before):
    assert set(bucket) == before                                   # no object left behind
    assert not CardDesignAsset.objects.filter(makerspace=target).exists()
    assert not CardTemplate.objects.filter(makerspace=target).exists()


def test_an_import_naming_a_missing_image_writes_nothing(bucket):
    source, target = card_space("m12-src"), card_space("m12-dst")
    exported = _exported(source, manager(source))
    exported["document"]["front"]["layers"][0]["asset_id"] = "ref:9"
    before = set(bucket)
    with pytest.raises(ValidationError):
        templates_files.import_file(manager(target, "imp"), target, exported)
    _refused_cleanly(bucket, target, before)


def test_an_invalid_document_writes_nothing(bucket):
    source, target = card_space("m12-bad-src"), card_space("m12-bad-dst")
    exported = _exported(source, manager(source))
    exported["document"]["stock"] = "not-a-stock"
    before = set(bucket)
    with pytest.raises(ValidationError):
        templates_files.import_file(manager(target, "imp"), target, exported)
    _refused_cleanly(bucket, target, before)


def test_an_unhashable_ref_is_a_400_not_a_500(bucket):
    source, target = card_space("m12-ref-src"), card_space("m12-ref-dst")
    exported = _exported(source, manager(source))
    exported["assets"][0]["ref"] = ["ref:1"]
    before = set(bucket)
    with pytest.raises(ValidationError):
        templates_files.import_file(manager(target, "imp"), target, exported)
    _refused_cleanly(bucket, target, before)


def test_a_storage_cap_refusal_writes_nothing(bucket, monkeypatch):
    source, target = card_space("m12-cap-src"), card_space("m12-cap-dst")
    exported = _exported(source, manager(source))

    def full(space, size):
        raise ValidationError({"detail": "storage full"})
    monkeypatch.setattr("apps.makerspaces.limits_usage.add_storage", full)
    before = set(bucket)
    with pytest.raises(ValidationError):
        templates_files.import_file(manager(target, "imp"), target, exported)
    _refused_cleanly(bucket, target, before)


def test_a_failed_write_deletes_the_images_already_written(bucket, monkeypatch):
    source, target = card_space("m12-put-src"), card_space("m12-put-dst")
    owner = manager(source)
    first = templates_files._create_asset(owner, source, "image", png((30, 30)))
    second = templates_files._create_asset(owner, source, "image", png((20, 20), colour=(10, 10, 200, 255)))
    design = _design(source, owner, document([layer("image", 5, 5, 20, 20, asset_id=first, fit="cover"),
                                              layer("image", 5, 30, 20, 20, asset_id=second, fit="cover")]))
    exported = templates_files.export_file(source, templates.create_from_design(owner, source, design, "Two"))
    before, calls = set(bucket), []

    def flaky(key, data, content_type):
        calls.append(key)
        if len(calls) == 2:
            raise OSError("storage down")
        bucket[key] = data
    monkeypatch.setattr(templates_files, "put_bytes", flaky)
    with pytest.raises(OSError):
        templates_files.import_file(manager(target, "imp"), target, exported)
    _refused_cleanly(bucket, target, before)


def test_a_valid_import_stores_each_image_once_and_charges_it(bucket):
    source, target = card_space("m12-ok-src"), card_space("m12-ok-dst")
    exported = _exported(source, manager(source))
    before = set(bucket)
    row = templates_files.import_file(manager(target, "imp"), target, exported)
    target.refresh_from_db()
    asset = CardDesignAsset.objects.get(makerspace=target)
    assert set(bucket) - before == {asset.object_key}
    assert target.storage_bytes_used >= asset.size_bytes
    assert row.document["front"]["layers"][0]["asset_id"] == str(asset.asset_id)


# --- L-M2 -------------------------------------------------------------------------------------------------------

def test_a_limited_template_quota_locks_the_space_row():
    space = card_space("lm2-tpl")
    owner = manager(space)
    design = _design(space, owner)
    _limit(space, **{templates.LIMIT_KEY: 5})
    with CaptureQueriesContext(connection) as queries:
        templates.create_from_design(owner, space, design, "Locked")
    assert any("FOR UPDATE" in q["sql"] and "makerspaces_makerspace" in q["sql"] for q in queries.captured_queries)
