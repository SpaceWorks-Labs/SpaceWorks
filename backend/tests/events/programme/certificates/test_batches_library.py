from uuid import uuid4
from copy import deepcopy

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.events.certificates.batches import enqueue, run_chunk
from apps.events.certificates.library import save, copy_to_event
from apps.events.certificates.library_models import EventCertificateLibraryRevision
from apps.events.models_feedback import EventFeedbackResponse
from tests.events.checkin_helpers import make_space, make_event, make_member, make_staff, register
from tests.events.programme.certificates.test_layers import document

pytestmark = pytest.mark.django_db(transaction=True)


def test_batch_replay_retains_subject_certificate_and_never_creates_feedback(monkeypatch):
    monkeypatch.setattr("apps.events.certificates.tasks.dispatch_batch", lambda batch_id: None)
    space = make_space("programme-batch")
    event, actor, member = make_event(space), make_staff(space), make_member(space)
    registration = register(event, member, status="attended")
    operation = uuid4()
    values = dict(actor=actor, operation_id=operation, expected_version=event.version, subjects=[],
                  all_attended=True, confirmed_count=1, publish_event_details=True)
    first = enqueue(event.pk, **values)
    assert enqueue(event.pk, **values).pk == first.pk
    first = run_chunk(first.pk)
    assert first.state == "completed" and first.items.count() == 1
    item = first.items.get()
    assert item.certificate.response_id is None and item.certificate.public_verification_enabled is True
    assert EventFeedbackResponse.objects.count() == 0
    assert run_chunk(first.pk).items.get().certificate_id == item.certificate_id


def test_library_is_tenant_scoped_and_copied_revisions_do_not_follow_later_edits():
    space = make_space("programme-library")
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=("enabled_features",))
    event, actor, member = make_event(space), make_staff(space), make_member(space)
    with pytest.raises(PermissionDenied):
        save(space.pk, actor=member, operation_id=uuid4(), expected_version=0, name="No authority", parameters=document())
    first = save(space.pk, actor=actor, operation_id=uuid4(), expected_version=0, name="Workshop", parameters=document())
    args = dict(actor=actor, template_id=first["id"], revision_id=first["revision_id"], event_id=event.pk,
                operation_id=uuid4(), expected_version=event.version)
    copied = copy_to_event(space.pk, **args)
    assert copy_to_event(space.pk, **args).pk == copied.pk
    changed = deepcopy(document())
    changed["layers"][0]["font_size_pt"] = 18
    save(space.pk, actor=actor, operation_id=uuid4(), expected_version=first["version"],
         name="Workshop", parameters=changed, template_id=first["id"])
    copied.refresh_from_db()
    assert copied.parameters["layers"][0]["font_size_pt"] == 24
    assert EventCertificateLibraryRevision.objects.count() == 2
