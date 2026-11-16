"""Exercise the ordinary encrypted portable importer with immutable designs."""

import hashlib
from datetime import timedelta
from io import BytesIO
from uuid import UUID

import pytest
from PIL import Image
from django.utils import timezone

from apps.events.certificate_templates import normalize_certificate_template
from apps.events.models import Event, EventCertificateArtwork, EventCertificateTemplateRevision
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration import object_storage
from apps.tenant_migration.models import TenantImportObject
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.events.test_lane_e_retention import issued
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import encryption_key, memory_objects
from tests.tenant_migration.test_object_content_types import _write_bundle

pytestmark = pytest.mark.django_db(transaction=True)


def test_encrypted_portable_roundtrip_keeps_layout_revisions_and_drops_staging_authority():
    parameters = normalize_certificate_template({})
    parameters["name_box"]["colour"] = "#123456"
    def designs(space, user, request):
        event = Event.objects.get(makerspace=space, title="Portable workshop")
        revision = EventCertificateTemplateRevision.objects.create(event=event, parameters=parameters)
        EventCertificateArtwork.objects.create(
            event=event, object_key=f"events/certificate-artwork/{space.pk}/unpromoted.png",
            size_bytes=10 * 1024 * 1024,
        )
        return revision.pk

    with enabled_encryption():
        user = make_user("design-roundtrip")
        source = make_space("design-roundtrip")
        with portable_import_case(source, user, prepare_source=designs) as case:
            case.decide_walk_in(user)
            result = materialize_tenant(case.root, case.job, case.carried,
                                       target_identity={"slug": "design-roundtrip-target"})
        revision = EventCertificateTemplateRevision.objects.get(event__makerspace_id=result.target_makerspace_id)
        assert revision.parameters == parameters
        assert revision.artwork_id is None
        assert not EventCertificateArtwork.objects.filter(event__makerspace_id=result.target_makerspace_id).exists()


def test_artwork_database_collision_remaps_manifest_row_snapshot_and_render(monkeypatch, memory_objects):
    from apps.events.certificate_artwork_storage import read_artwork
    from apps.events.certificate_rendering import render_certificate_pdf
    from apps.events.models import EventAttendanceCertificate

    image = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format="PNG")
    payload = image.getvalue()
    digest = hashlib.sha256(payload).hexdigest()

    def designs(space, user, request):
        event = Event.objects.get(makerspace=space, title="Portable workshop")
        artwork = EventCertificateArtwork.objects.create(
            event=event, object_key="events/certificate-artwork/source/collision.png",
            size_bytes=len(payload), sha256=digest, version_id="source-version",
            promoted_at=timezone.now(),
        )
        _revision, certificate = issued(event, artwork)
        return artwork, certificate

    with enabled_encryption():
        user = make_user("artwork-collision")
        source = make_space("artwork-collision")
        with portable_import_case(source, user, prepare_source=designs) as case:
            artwork, certificate = case.source_data
            source_key = artwork.object_key
            # The target database reserves the source key but has no final bytes.
            # Source rows stay in this test DB to simulate that target collision.
            assert source_key not in memory_objects["private"]
            _write_bundle(case.root, [
                ({"bucket_kind": "private", "source_key": source_key,
                  "content_type": "image/png"}, payload),
                ({"bucket_kind": "private", "source_key": certificate.object_key,
                  "content_type": "application/pdf"}, b"%PDF immutable source certificate"),
            ])
            case.decide_walk_in(user)
            case.release_non_regenerable_identities()
            # Releasing the source's immutable identities (artwork resource_id) also
            # removed its rows; a different target-side artwork keeps holding the same
            # object key, so the import still meets the key collision it must remap.
            holder_space = make_space("artwork-collision-holder")
            holder = Event.objects.create(makerspace=holder_space, title="Key holder",
                starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1))
            held = EventCertificateArtwork.objects.create(event=holder, object_key=source_key)
            result = materialize_tenant(case.root, case.job, case.carried,
                                       target_identity={"slug": "artwork-collision-target"})
            journal = TenantImportObject.objects.get(job=case.job, source_key=source_key)

        imported = EventCertificateArtwork.objects.get(event__makerspace_id=result.target_makerspace_id)
        frozen = EventAttendanceCertificate.objects.get(registration__event=imported.event)
        assert imported.object_key == frozen.layout_snapshot["artwork_object_key"] == journal.target_key
        assert imported.object_key != source_key
        assert journal.state == TenantImportObject.State.VERIFIED
        assert imported.version_id == frozen.layout_snapshot["artwork_version_id"] == ""
        assert imported.sha256 == frozen.layout_snapshot["artwork_sha256"] == digest
        assert memory_objects["private"][imported.object_key] == payload
        assert source_key not in memory_objects["private"]
        # The target-side row that held the key is untouched by the remapping import.
        held.refresh_from_db()
        assert held.object_key == source_key and held.version_id == ""

        monkeypatch.setattr("apps.events.certificate_artwork_storage._client", lambda endpoint: None)
        monkeypatch.setattr("apps.events.certificate_artwork_storage._read",
                            lambda client, key, version="": (memory_objects["private"][key], ""))
        assert read_artwork(imported.object_key, imported.version_id, imported.sha256) == payload
        assert render_certificate_pdf(frozen).startswith(b"%PDF")


@pytest.mark.parametrize("promoted", [False, True])
def test_manifest_allocation_checks_database_reservations_for_every_candidate(monkeypatch, promoted):
    from tests.events.ticketing_helpers import event_space, open_event

    event = open_event(event_space("manifest-reservations"))
    source_key = "events/certificate-artwork/source/reserved.png"
    candidate = f"migrated-objects/job/{UUID(int=1).hex}"
    for key in (source_key, candidate):
        EventCertificateArtwork.objects.create(
            event=event, object_key=key, promoted_at=timezone.now() if promoted else None,
        )
    monkeypatch.setattr(object_storage, "object_exists", lambda kind, key: False)
    values = iter([UUID(int=1), UUID(int=2)])
    monkeypatch.setattr(object_storage.uuid, "uuid4", lambda: next(values))

    assert object_storage.choose_target_key("private", source_key, "job") == (
        f"migrated-objects/job/{UUID(int=2).hex}", True,
    )
    assert object_storage.choose_target_key("private", "unused.png", "job") == ("unused.png", False)
    assert object_storage.choose_target_key("public_image", source_key, "job") == (source_key, False)
