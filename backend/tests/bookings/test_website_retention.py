"""Concrete models travel as editorial data; release and object trust stay target-owned."""

import hashlib
import json
from pathlib import Path

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.bookings.models_website import BookingResourcePage, BookingResourcePageAsset, BookingResourcePageSection
from apps.makerspaces import website_assets
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration.object_export import object_member_path
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import memory_objects  # noqa: F401 -- fixture


def test_catalog_feature_and_object_contracts():
    from django.apps import apps
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.datasets import DATASET_SPECS
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.setup_areas import features_for
    from apps.tenant_migration.tenant_dump_catalog import CATALOG_SCHEMA_SHA256, schema_digest
    assert schema_digest() == CATALOG_SCHEMA_SHA256
    rules = validate_object_reference_registry()
    assert any(row.model_label == "bookings.BookingResourcePageAsset" for row in rules)
    for label in ("bookings.BookingResourcePage", "bookings.BookingResourcePageAsset", "bookings.BookingResourcePageSection"):
        assert label in EXPORTED_MODEL_FIELDS and label in DATASET_SPECS
        assert not any(f.is_relation and f.related_model._meta.label == "accounts.User"
                       for f in apps.get_model(label)._meta.concrete_fields)
    for key in ("bookings.website", "bookings.embed"):
        assert FEATURES[key].parent_module == "bookings" and not FEATURES[key].default_enabled
        assert key in features_for({"bookings"}) and key not in features_for({"events"})
    # Runtime booking mechanisms have no separable event dependency.
    root = Path(__file__).resolve().parents[3] / "backend/apps/bookings"
    assert all("apps.events" not in path.read_text() for path in root.glob("*website*.py"))


@pytest.mark.django_db(transaction=True)
def test_portable_page_asset_and_section_roundtrip_reset_release(memory_objects):
    data = b"portable private website bytes"
    with enabled_encryption():
        user, source = make_user("resource-page-export"), make_space("resource-page-export")
        source.enabled_modules = sorted(set(source.enabled_modules) | {"bookings"})
        source.enabled_features = ["bookings.website", "bookings.embed"]
        source.save()
        resource = BookableSpace.objects.create(makerspace=source, name="Portable room", is_public=True)
        page = BookingResourcePage.objects.create(space=resource, released=True)
        key = f"bookings/website/{source.pk}/{page.pk}/portable.webp"
        asset = BookingResourcePageAsset.objects.create(page=page, object_key=key, alt_text="Portable", size_bytes=len(data))
        BookingResourcePageSection.objects.create(page=page, kind="gallery", slug="gallery", title="Gallery",
                                                   body="**Safe** content", visibility="published", asset=asset)
        with portable_import_case(source, user) as case:
            case.decide_walk_in(user)
            case.release_non_regenerable_identities()
            # The unpackaged test archive carries rows only; add the private object
            # member and manifest line exactly as object capture would write them.
            member = Path(case.root) / object_member_path("private", key)
            member.parent.mkdir(parents=True, exist_ok=True)
            member.write_bytes(data)
            manifest = Path(case.root) / "objects/manifest.jsonl"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps({"bucket_kind": "private", "source_key": key,
                "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "version_id": "source-version", "content_type": "image/webp"}) + "\n")
            result = materialize_tenant(case.root, case.job, case.carried,
                                       target_identity={"slug": "resource-page-target"})
        imported = BookingResourcePage.objects.select_related("space__makerspace").get(
            space__makerspace_id=result.target_makerspace_id)
        assert not imported.released and imported.pk != page.pk
        copied = imported.assets.get()
        assert imported.sections.get().asset == copied
        assert imported.sections.get().body == "**Safe** content"
        # The source row reserves its key even when its bytes are absent in the
        # target store. Import chooses a fresh key, trusted via the object journal.
        assert copied.object_key != key
        assert memory_objects["private"][copied.object_key] == data
        assert website_assets.owns(copied.object_key, "bookings", imported.makerspace_id, imported.pk, asset=copied)


@pytest.mark.django_db
def test_missing_website_bytes_do_not_release_an_asset_rows_private_key(memory_objects):
    from apps.tenant_migration.object_storage import choose_target_key
    source = make_space("resource-page-reserved-key")
    resource = BookableSpace.objects.create(makerspace=source, name="Reserved room")
    page = BookingResourcePage.objects.create(space=resource)
    key = f"bookings/website/{source.pk}/{page.pk}/reserved.webp"
    BookingResourcePageAsset.objects.create(page=page, object_key=key, alt_text="Reserved", size_bytes=10)
    assert key not in memory_objects["private"]
    target_key, changed = choose_target_key("private", key, "reserved-test")
    assert changed and target_key != key


@pytest.mark.django_db(transaction=True)
def test_module_and_tenant_purge_collect_private_gallery_tenant_locally(monkeypatch):
    from apps.accounts.models import User
    from apps.makerspaces.lifecycle_purge import purge
    from apps.makerspaces.module_install import uninstall_module
    from apps.makerspaces.module_purge import purge_module
    from apps.makerspaces.storage_key_collectors import collect_private_object_keys
    from apps.makerspaces.module_purge_collectors_booking_website import bookings_private_key_sizes
    from tests.bookings.website_helpers import world, image, memory_storage
    from apps.bookings.services_website_assets import upload_asset
    w, foreign = world(), world(slug="website-purge-other")
    objects, _ = memory_storage(monkeypatch)
    asset = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Owned")
    other = upload_asset(foreign.resource, actor=foreign.actor, file=image(), alt_text="Foreign")
    assert asset.object_key in collect_private_object_keys(w.tenant)
    assert other.object_key not in collect_private_object_keys(w.tenant)
    assert bookings_private_key_sizes(w.tenant) == {asset.object_key: asset.size_bytes}
    root = User.objects.create_superuser(username="website-purge-root", email="root@example.test", password="pw")
    monkeypatch.setattr("apps.makerspaces.module_purge._delete_private_keys", lambda keys: {
        key for key in keys if website_assets.delete_object(key)})
    uninstall_module(w.tenant, "bookings")
    assert BookingResourcePage.objects.filter(space=w.resource).exists()
    purge_module(w.tenant, "bookings", root)
    assert not BookingResourcePage.objects.filter(space_id=w.resource.pk).exists()
    assert asset.object_key not in objects and other.object_key in objects
    assert BookingResourcePage.objects.filter(space=foreign.resource).exists()
    foreign.tenant.archived_at = timezone.now()
    foreign.tenant.save()
    # Whole-tenant collector independently names the same private key before cascading rows.
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_storage_keys", lambda keys: [website_assets.delete_object(key) for key in keys])
    purge(foreign.tenant, root)
    assert not BookingResourcePage.objects.filter(space_id=foreign.resource.pk).exists()
