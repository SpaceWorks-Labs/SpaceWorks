import hashlib
from copy import deepcopy
from uuid import uuid4

import pytest
from django.db import connection
from django.utils import timezone
from apps.events.certificates.library_capture import capture
from apps.events.certificates.library_models import EventCertificateLibraryArtwork, EventCertificateLibraryRevision
from apps.events.models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from tests.events.checkin_helpers import make_space, make_event, make_staff
from tests.events.programme.certificates.test_layers import document

pytestmark = pytest.mark.django_db(transaction=True)


def test_event_artwork_is_independently_copied_outside_locks_and_replay_does_not_copy_twice(monkeypatch):
    space = make_space("library-artwork-copy")
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=("enabled_features",))
    event, actor = make_event(space), make_staff(space)
    content = b"canonical image bytes already validated by artwork promotion"
    digest = hashlib.sha256(content).hexdigest()
    source = EventCertificateArtwork.objects.create(event=event, object_key=f"events/{space.pk}/source.png",
        promoted_at=timezone.now(), sha256=digest, size_bytes=len(content))
    parameters = document()
    parameters["layers"].append({"id": str(uuid4()), "order": 4, "type": "image", "resource_id": str(source.resource_id),
        "x_mm": 10, "y_mm": 10, "width_mm": 40, "height_mm": 30, "rotation": 0})
    revision = EventCertificateTemplateRevision.objects.create(event=event, parameters=parameters)
    writes = []
    def read(*args):
        assert not connection.in_atomic_block
        return content
    def put(key, payload, mime):
        assert not connection.in_atomic_block
        assert payload == content and mime == "image/png"
        writes.append(key)
        return len(payload), digest
    monkeypatch.setattr("apps.events.certificates.library_capture.storage.read_artwork", read)
    monkeypatch.setattr("apps.events.certificates.library_capture.print_storage.put", put)
    values = dict(actor=actor, operation_id=uuid4(), expected_version=0, event_id=event.pk,
                  revision_id=revision.pk, name="Independent library design")
    first = capture(space.pk, **values)
    assert capture(space.pk, **values) == first and len(writes) == 1
    artwork = EventCertificateLibraryArtwork.objects.get(template_id=first["id"])
    assert artwork.object_key != source.object_key and artwork.sha256 == source.sha256
    assert first["parameters"]["layers"][-1]["resource_id"] == str(artwork.resource_id)
    assert str(artwork.resource_id) != str(source.resource_id)
    again = capture(space.pk, **{**values, "operation_id": uuid4(), "template_id": first["id"], "expected_version": 1})
    assert again["version"] == 2 and EventCertificateLibraryRevision.objects.count() == 2
    assert EventCertificateLibraryRevision.objects.get(pk=first["revision_id"]).parameters == first["parameters"]
