"""Old certificate image layers store a `resource_id` UUID; the by-resource read route resolves it inside the event only."""
import pytest
from django.http import Http404
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.events import views_certificate_templates as views
from apps.events.models import Event, EventCertificateArtwork
from tests.events.staff_grant_helpers import grant_fixture


def _row(event, key, promoted=True):
    return EventCertificateArtwork.objects.create(
        event=event, object_key=f"events/certificate-artwork/{event.makerspace_id}/{key}.png", size_bytes=3,
        sha256="a" * 64, promoted_at=timezone.now() if promoted else None)


def _get(user, event, resource_id):
    request = APIRequestFactory().get("/x")
    force_authenticate(request, user=user)
    return views.EventCertificateArtworkByResourceView.as_view()(request, pk=event.pk, resource_id=resource_id)


@pytest.fixture
def bytes_read(monkeypatch):
    monkeypatch.setattr(views.storage, "read_artwork", lambda key, version, sha: b"PNGBYTES")
    monkeypatch.setattr(views, "_event", lambda request, pk: Event.objects.get(pk=pk))


@pytest.mark.django_db
def test_resource_id_resolves_to_the_private_bytes(bytes_read):
    space, manager, editor, event, grant = grant_fixture()
    row = _row(event, "one")
    response = _get(editor, event, row.resource_id)
    assert response.status_code == 200 and response.content == b"PNGBYTES"
    assert response["Cache-Control"] == "private, no-store" and response["Content-Type"] == "image/png"


@pytest.mark.django_db
def test_another_events_resource_id_is_a_404(bytes_read):
    space, manager, editor, event, grant = grant_fixture()
    _s2, _m2, _e2, other, _g2 = grant_fixture(slug="event-grants-2", grantee="event-grantee-2")
    foreign = _row(other, "two")
    # DRF turns the view's Http404 into a 404 response rather than letting it propagate.
    assert _get(editor, event, foreign.resource_id).status_code == 404


@pytest.mark.django_db
def test_unpromoted_artwork_is_a_404(bytes_read):
    space, manager, editor, event, grant = grant_fixture()
    row = _row(event, "three", promoted=False)
    assert _get(editor, event, row.resource_id).status_code == 404
