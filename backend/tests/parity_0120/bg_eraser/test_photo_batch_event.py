"""D314c addendum, event cards: the bulk photo upload is an event-organiser surface (event authority, not space cards)."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.card_designs import designs, photo_batch_apply, resolution
from apps.card_designs.models import CardPhotoBatch
from apps.events import id_cards
from apps.events.models import Event, EventIdCard, EventRegistration
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

from .conftest import jpeg

pytestmark = pytest.mark.django_db


def _event(slug):
    space = card_space(slug, features=("events.id_cards",))
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Build Night", starts_at=now - timezone.timedelta(hours=1),
                                 ends_at=now + timezone.timedelta(hours=3), status="published")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    designs.publish(sm, design)
    cards = {}
    for name in ("asha", "ravi"):
        user, _m = member(space, name)
        EventRegistration.objects.create(event=event, member=user, name=name, email=user.email,
                                         status=EventRegistration.Status.REGISTERED)
    id_cards.reconcile_event(event.pk)
    for card in EventIdCard.objects.filter(event=event).select_related("person"):
        card.printed_name = "Asha Nair" if card.person.username.startswith("asha") else "Ravi Menon"
        card.save(update_fields=["printed_name"])
        cards[card.printed_name] = card
    return space, event, sm, cards


def _urls(space, *rest):
    if not rest:
        return reverse("admin-card-photo-batches", args=[space.pk])
    return reverse(rest[0], args=[space.pk, *rest[1:]])


def _body(event, **extra):
    return {"kind": "event_card", "event_id": event.pk, "holders_consented": True, **extra}


@pytest.fixture
def attached(monkeypatch):
    calls = []
    monkeypatch.setattr("apps.card_designs.photos.attach_bytes",
                        lambda actor, kind, card, data, *, consent: calls.append((kind, card.pk, consent)) or card)
    return calls


def test_an_event_organiser_matches_by_name_and_applies_through_the_event_photo_path(store, attached):
    space, event, sm, cards = _event("pbe-apply")
    api = client(sm)
    created = api.post(_urls(space), _body(event), format="json")
    assert created.status_code == 201 and created.json()["event_id"] == event.pk
    batch_id = created.json()["id"]
    uploads = [SimpleUploadedFile("asha nair.jpg", jpeg()), SimpleUploadedFile("RAVI_MENON.png", jpeg()),
               SimpleUploadedFile("someone else.jpg", jpeg())]
    body = api.post(_urls(space, "admin-card-photo-batch-files", batch_id), {"files": uploads}, format="multipart").json()
    assert sorted(item["status"] for item in body["items"]) == ["matched", "matched", "unmatched"]
    assert {holder["name"] for holder in body["holders"]} == {"Asha Nair", "Ravi Menon"}
    assert api.post(_urls(space, "admin-card-photo-batch-apply", batch_id)).status_code == 202
    photo_batch_apply.apply_chunk(batch_id)
    assert sorted(pk for _k, pk, _c in attached) == sorted(card.pk for card in cards.values())
    assert all(kind == "event_card" and consent for kind, _pk, consent in attached)  # the batch's consent rides along
    assert CardPhotoBatch.objects.get(pk=batch_id).applied_count == 2


def test_an_event_batch_needs_the_event_and_the_organiser_authority(store):
    space, event, sm, _cards = _event("pbe-rbac")
    assert client(sm).post(_urls(space), {"kind": "event_card", "holders_consented": True}, format="json").status_code == 400
    door = custom_staff(space, ["handover"], "door")  # staff without event authority
    assert client(door).post(_urls(space), _body(event), format="json").status_code in (403, 404)
    other_space, other_event, other_sm, _ = _event("pbe-rbac-other")
    assert client(other_sm).post(_urls(space), _body(event), format="json").status_code in (403, 404)
    # An event of another space is never reachable through this space's route.
    assert client(sm).post(_urls(space), _body(other_event), format="json").status_code in (403, 404)
    assert not CardPhotoBatch.objects.exists()
    assert other_space.pk != space.pk


def test_event_batch_holders_are_only_that_events_active_cards(store):
    space, event, sm, cards = _event("pbe-scope")
    EventIdCard.objects.filter(pk=cards["Ravi Menon"].pk).update(status="revoked", revoked_at=timezone.now())
    api = client(sm)
    batch_id = api.post(_urls(space), _body(event), format="json").json()["id"]
    body = api.get(_urls(space, "admin-card-photo-batch", batch_id)).json()
    assert [holder["name"] for holder in body["holders"]] == ["Asha Nair"]
