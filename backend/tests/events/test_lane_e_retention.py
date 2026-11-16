"""Credential designs retain private bytes and portable issuance identities."""

from apps.accounts.models import User
from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection, transaction
from django.utils import timezone

from apps.events.certificate_artwork_storage import MAX_BYTES
from apps.events.certificate_templates import normalize_certificate_template, issuance_layout
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.data_export.datasets import DATASET_SPECS
from apps.encryption.registry import fields_for_label
from apps.events.models import (
    EventAttendanceCertificate, EventCertificateArtwork, EventCertificateTemplateRevision,
    EventFeedbackResponse, EventFeedbackSurvey, EventRegistration,
)
from apps.makerspaces.module_purge_collectors_events import (
    events_delete, events_private_keys, events_private_key_sizes,
)
from apps.makerspaces.storage_key_collectors import collect_private_object_keys
from apps.tenant_migration.insertion_errors import ArchiveFormatError
from apps.tenant_migration.object_fields import rewrite_object_fields
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from tests.events.ticketing_helpers import event_space, open_event

LABELS = ("events.EventCertificateArtwork", "events.EventCertificateTemplateRevision")
QUESTION = {"id": "rating", "label": "Rating", "type": "number",
            "options": [], "required": False}


@pytest.mark.parametrize("label", LABELS)
def test_design_models_are_classified_without_pii_or_live_user_edges(label):
    model = apps.get_model(label)
    actual = {f.name for f in model._meta.get_fields() if f.concrete or f.many_to_many}
    assert set(EXPORTED_MODEL_FIELDS[label].split()) == actual
    assert FIRST_PARTY_FIELD_NAMES[label] == actual
    assert DATASET_SPECS[label][1].any_paths == ("event__makerspace",)
    assert not fields_for_label(label)
    assert not any(f.is_relation and f.related_model is not None
                   and f.related_model._meta.label == "accounts.User"
                   for f in model._meta.concrete_fields)


def test_snapshot_remaps_key_and_drops_source_bucket_version_without_mutating_source():
    row = {"object_key": "issued.pdf", "layout_snapshot": {
        "version": 1, "artwork_object_key": "design.png", "artwork_version_id": "source-v1",
        "artwork_sha256": "a" * 64, "name_box": {"x_mm": 20},
    }}
    original = deepcopy(row["layout_snapshot"])
    rewrite_object_fields(EventAttendanceCertificate, row,
                          {"issued.pdf": "target.pdf", "design.png": "target.png"})
    assert row["object_key"] == "target.pdf"
    assert row["layout_snapshot"] == {**original, "artwork_object_key": "target.png",
                                      "artwork_version_id": ""}
    assert original["artwork_version_id"] == "source-v1"


@pytest.mark.parametrize("snapshot", [{"artwork_object_key": "absent.png"}, [], None])
def test_unaccounted_artwork_snapshot_refuses_portable_import(snapshot):
    with pytest.raises(ArchiveFormatError):
        rewrite_object_fields(EventAttendanceCertificate,
                              {"object_key": "", "layout_snapshot": snapshot}, {})


def test_unpromoted_artwork_is_not_portable_and_version_identity_is_reset():
    from apps.tenant_migration.admission import export_row_policy
    from apps.tenant_migration.row_dispositions import row_disposition
    from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
    assert export_row_policy(LABELS[0], SimpleNamespace(promoted_at=None)) == (False, False)
    assert row_disposition(LABELS[0], {"promoted_at": None}, None) == "drop"
    assert export_row_policy(LABELS[0], SimpleNamespace(promoted_at=timezone.now())) == (True, True)
    assert TARGET_FIELD_PROJECTION[(LABELS[0], "version_id")].value == ""


def design(event, *, promoted=True):
    return EventCertificateArtwork.objects.create(
        event=event, object_key=f"events/certificate-artwork/{event.makerspace_id}/{event.pk}-{promoted}.png",
        size_bytes=123 if promoted else MAX_BYTES, sha256="a" * 64 if promoted else "",
        version_id="v1" if promoted else "", promoted_at=timezone.now() if promoted else None,
    )


def issued(event, artwork):
    revision = EventCertificateTemplateRevision.objects.create(
        event=event, artwork=artwork, parameters=normalize_certificate_template({}),
    )
    registration = EventRegistration.objects.create(event=event, name="Recipient", status="attended")
    survey = EventFeedbackSurvey.objects.create(
        event=event, title="Feedback", questions=[QUESTION], certificate_enabled=True,
    )
    response = EventFeedbackResponse.objects.create(
        survey=survey, registration=registration, certificate_requested=True,
        answers_snapshot='{"version":1,"answers":[{"id":"rating","value":4}]}',
    )
    certificate = EventAttendanceCertificate.objects.create(
        registration=registration, response=response, revision=1, template_revision=revision,
        recipient_name="Recipient", event_title=event.title, event_starts_at=event.starts_at,
        event_ends_at=event.ends_at, issuer_name="Lab", object_key=f"issued/{event.pk}.pdf",
        layout_snapshot=issuance_layout(revision),
    )
    return revision, certificate


@pytest.mark.django_db
def test_scoped_storage_closure_keeps_staging_for_purge_and_only_promoted_for_capture():
    space, other = event_space("art-owned"), event_space("art-other")
    event, foreign = open_event(space), open_event(other)
    artwork, unpromoted, outside = design(event), design(event, promoted=False), design(foreign)
    purge = collect_private_object_keys(space)
    capture = collect_private_object_keys(space, include_coordination=False)
    assert artwork.object_key in capture
    assert unpromoted.object_key not in capture
    assert f"staging/{artwork.object_key}" in purge
    assert f"staging/{unpromoted.object_key}" in purge
    assert outside.object_key not in purge
    module_keys = []
    events_private_keys(space, module_keys.append)
    assert set(module_keys) == {artwork.object_key, unpromoted.object_key,
                               f"staging/{artwork.object_key}", f"staging/{unpromoted.object_key}"}
    assert events_private_key_sizes(space) == {artwork.object_key: 123, unpromoted.object_key: MAX_BYTES}


@pytest.mark.django_db
def test_module_purge_deletes_certificates_before_protected_designs_and_keeps_other_tenant():
    space, other = event_space("art-purge"), event_space("art-keep")
    artwork, outside = design(open_event(space)), design(open_event(other))
    revision, certificate = issued(artwork.event, artwork)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        counts = events_delete(space, cursor)
    assert not EventAttendanceCertificate.objects.filter(pk=certificate.pk).exists()
    assert not EventCertificateTemplateRevision.objects.filter(pk=revision.pk).exists()
    assert not EventCertificateArtwork.objects.filter(pk=artwork.pk).exists()
    assert EventCertificateArtwork.objects.filter(pk=outside.pk).exists()
    assert counts["event_certificate_artwork"] == 1


@pytest.mark.django_db
def test_snapshot_ownership_sites_join_artwork_owner_and_skip_legacy_empty_layout():
    from apps.backup.object_reference_certificates import certificate_snapshot_references
    space = event_space("art-backup")
    artwork = design(open_event(space))
    revision, certificate = issued(artwork.event, artwork)
    sites = list(certificate_snapshot_references())
    match = next(site for site in sites if site.object_key == artwork.object_key)
    assert match.candidate_owner == "main"
    assert match.canonical_makerspace_id == space.pk
    assert match.bucket_kind == "private"


@pytest.mark.django_db
def test_backup_excludes_unpromoted_upload_reservations():
    from apps.backup.archive_objects import collect_model_objects
    space = event_space("art-backup-reservation")
    event = open_event(space)
    artwork, pending = design(event), design(event, promoted=False)
    result = {"private": {}, "public_image": {}}
    collect_model_objects(EventCertificateArtwork.objects.filter(event=event),
                          EventCertificateArtwork, result)
    assert set(result["private"]) == {artwork.object_key}
    assert result["private"][artwork.object_key] == {"makerspace_id": space.pk, "module_key": "events"}


def test_live_catalog_and_object_registry_cover_the_design_graph():
    from apps.backup.object_ownership_registry import validate_object_reference_registry
    from apps.tenant_migration.tenant_dump_catalog import validate_catalog
    from apps.tenant_migration.projection_guards import validate_projection_fk_registry
    validate_catalog()
    validate_object_reference_registry()
    validate_projection_fk_registry()


@pytest.mark.django_db
def test_whole_tenant_purge_preserves_foreign_artwork_and_collects_staged_uploads(monkeypatch, django_capture_on_commit_callbacks):
    from apps.makerspaces.lifecycle_purge import purge
    from tests.events.collab_helpers import make_staff
    space, other = event_space("art-tenant-purge"), event_space("art-tenant-keep")
    artwork, outside = design(open_event(space)), design(open_event(other))
    revision, certificate = issued(artwork.event, artwork)
    pending = design(artwork.event, promoted=False)
    actor = User.objects.create_superuser(username="event-purge-root", password=None)
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    deleted = []
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_storage_keys", deleted.extend)
    monkeypatch.setattr("apps.makerspaces.lifecycle._delete_public_image_keys", lambda keys: None)
    # Object deletion runs only after the purge commits.
    with django_capture_on_commit_callbacks(execute=True):
        purge(space, actor)
    assert not EventCertificateArtwork.objects.filter(pk=artwork.pk).exists()
    assert not EventCertificateTemplateRevision.objects.filter(pk=revision.pk).exists()
    assert not EventAttendanceCertificate.objects.filter(pk=certificate.pk).exists()
    assert EventCertificateArtwork.objects.filter(pk=outside.pk).exists()
    assert {artwork.object_key, pending.object_key, f"staging/{pending.object_key}"} <= set(deleted)
    assert outside.object_key not in deleted


@pytest.mark.django_db
def test_storage_reconciler_counts_promoted_artwork_once(monkeypatch):
    from django.core.management import call_command
    space = event_space("art-quota")
    event = open_event(space)
    artwork = design(event)
    design(event, promoted=False)
    observed = []
    def size(key):
        observed.append(key)
        return 123
    monkeypatch.setattr("apps.evidence.storage.object_size", size)
    call_command("recompute_storage", space.slug)
    space.refresh_from_db()
    assert space.storage_bytes_used == 123 + MAX_BYTES
    assert observed == [artwork.object_key]


# Pages: the release first checks the page cleanup journal, which reads the database.
@pytest.mark.django_db
def test_artwork_reservation_release_requires_final_and_staging_deletion(monkeypatch):
    from unittest.mock import Mock
    from apps.makerspaces.module_purge import _free_private_storage
    free = Mock()
    monkeypatch.setattr("apps.makerspaces.limits.free_storage", free)
    key = "events/certificate-artwork/1/owned.png"
    space = SimpleNamespace(pk=1)
    _free_private_storage(space, {key: MAX_BYTES}, {key})
    free.assert_not_called()
    _free_private_storage(space, {key: MAX_BYTES}, {key, f"staging/{key}"})
    free.assert_called_once_with(space, MAX_BYTES)
