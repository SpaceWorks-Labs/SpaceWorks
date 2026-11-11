import hashlib
from uuid import uuid4

import pytest
from django.db import connection

from apps.events.certificates.print_models import BadgePrintResource
from apps.events.certificates.print_workflow import create, prepare_resources
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.selection_workflow import source_revision
from apps.events.profile_photos.snapshot import PreparedPhoto
from apps.makerspaces.models_profiles import MemberProfile
from tests.events.programme.certificates.test_print_policy import desk

pytestmark = pytest.mark.django_db(transaction=True)


def photo_job(desk):
    event, actor, registration, _, values = desk
    space = event.makerspace
    if "membership" not in space.enabled_modules:
        space.enabled_modules = [*space.enabled_modules, "membership"]
        space.save(update_fields=["enabled_modules"])
    membership = registration.member.makerspace_memberships.get(makerspace=space)
    profile = MemberProfile.objects.create(membership=membership, avatar_key="member/g2b/portrait.png")
    presentation = EventMemberPresentation.objects.create(event=event, member=registration.member,
        selected_profile=profile, selected_membership=membership, print_photo_consent=True,
        source_revision=source_revision(profile), version=1)
    job = create(event.pk, actor=actor, **{key: value for key, value in values.items()
        if key not in ("operation_id", "include_photo")}, operation_id=uuid4(), include_photo=True)
    pixels = b"canonical-immutable-test-pixels"
    prepared = PreparedPhoto(profile_id=profile.pk, membership_id=membership.pk,
        source_revision=source_revision(profile), source_key_digest=hashlib.sha256(profile.avatar_key.encode()).hexdigest(),
        sha256=hashlib.sha256(pixels).hexdigest(), pixels=pixels)
    return actor, registration, job, presentation, prepared


def test_consent_revoked_during_outside_transaction_photo_read_never_binds_or_uploads(desk, monkeypatch):
    actor, registration, job, presentation, photo = photo_job(desk)
    puts = []
    monkeypatch.setattr("apps.events.certificates.print_logo.prepare_logo", lambda *args: None)
    monkeypatch.setattr("apps.events.certificates.print_workflow.storage.put", lambda *args: puts.append(args))
    def prepare(profile):
        assert not connection.in_atomic_block
        EventMemberPresentation.objects.filter(pk=presentation.pk).update(print_photo_consent=False, version=2)
        return photo
    monkeypatch.setattr("apps.events.certificates.print_workflow.prepare_photo", prepare)
    with pytest.raises(ProgrammeConflict):
        prepare_resources(job, actor=actor)
    assert not puts and not job.resources.filter(kind="photo").exists()


def test_preexisting_immutable_reservation_cannot_be_written_with_different_prepared_pixels(desk, monkeypatch):
    actor, registration, job, presentation, photo = photo_job(desk)
    resource = BadgePrintResource.objects.create(job=job, registration=registration, kind="photo",
        presentation=presentation, presentation_version=presentation.version, source_profile_id=photo.profile_id,
        source_avatar_revision=photo.source_revision, source_key_sha256=photo.source_key_digest,
        object_key=f"events/badge-print/{uuid4()}.png", sha256="0" * 64, size_bytes=len(photo.pixels),
        expires_at=job.expires_at)
    puts = []
    monkeypatch.setattr("apps.events.certificates.print_logo.prepare_logo", lambda *args: None)
    monkeypatch.setattr("apps.events.certificates.print_workflow.prepare_photo", lambda *args: photo)
    monkeypatch.setattr("apps.events.certificates.print_workflow.storage.put", lambda *args: puts.append(args))
    with pytest.raises(ProgrammeConflict):
        prepare_resources(job, actor=actor)
    resource.refresh_from_db()
    assert not puts and resource.bound_at is None and resource.sha256 == "0" * 64
