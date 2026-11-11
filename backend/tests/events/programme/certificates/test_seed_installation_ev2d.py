from hashlib import sha256

import pytest
from django.db import connection

from apps.events.certificates.seeds import install_to_event
from apps.events.certificates.print_models import EventBadgeTemplateRevision
from apps.events.models_certificate_templates import EventCertificateArtwork
from apps.events.certificate_templates import issuance_layout
from tests.events.staff_grant_helpers import grant_fixture


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind,seed_id,stock", [("certificate", "certificate-foundry", None),
                                               ("badge", "badge-classic", "cr80-landscape")])
def test_seed_replay_has_independent_event_owned_immutable_artwork_and_no_io_under_locks(monkeypatch, kind, seed_id, stock):
    space, manager, _, event, _ = grant_fixture()
    from apps.events.certificates import print_storage
    objects = {}
    def put(key, payload, mime):
        assert not connection.in_atomic_block
        if key in objects:
            assert objects[key] == payload
        objects[key] = payload
        return len(payload), sha256(payload).hexdigest()
    monkeypatch.setattr(print_storage, "put", put)
    args = dict(actor=manager, seed_id=seed_id, kind=kind, theme="dark", stock=stock)
    first = install_to_event(event.pk, **args)
    replay = install_to_event(event.pk, **args)
    assert replay.pk == first.pk and len(objects) == 1
    artwork = EventCertificateArtwork.objects.get(event=event)
    assert artwork.promoted_at and artwork.sha256 == sha256(objects[artwork.object_key]).hexdigest()
    doc = first.document if kind == "badge" else first.parameters
    assert doc["layers"][0]["resource_id"] == str(artwork.resource_id)
    if kind == "certificate":
        assert issuance_layout(first)["artwork_resources"][str(artwork.resource_id)]["key"] == artwork.object_key
    else:
        assert EventBadgeTemplateRevision.objects.filter(event=event).count() == 1


@pytest.mark.django_db(transaction=True)
def test_failed_seed_upload_retains_owned_row_and_retry_reuses_it(monkeypatch):
    _, manager, _, event, _ = grant_fixture()
    from apps.events.certificates import print_storage
    monkeypatch.setattr(print_storage, "put", lambda *a: (_ for _ in ()).throw(print_storage.PrintStorageUnavailable()))
    args = dict(actor=manager, seed_id="certificate-contour", kind="certificate", theme="light")
    with pytest.raises(print_storage.PrintStorageUnavailable):
        install_to_event(event.pk, **args)
    before = EventCertificateArtwork.objects.get(event=event)
    assert before.promoted_at is None
    monkeypatch.setattr(print_storage, "put", lambda key, content, mime: (len(content), sha256(content).hexdigest()))
    installed = install_to_event(event.pk, **args)
    after = EventCertificateArtwork.objects.get(event=event)
    assert after.pk == before.pk and after.promoted_at
    assert installed.parameters["layers"][0]["resource_id"] == str(after.resource_id)
