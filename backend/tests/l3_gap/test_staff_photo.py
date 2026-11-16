"""X25 / P21: staff capture or upload a holder's card photo, with the holder's consent, through the
same staging-then-promote rule as the holder's own upload, for all three card kinds."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs.models import CardPhotoRequest
from apps.makerspaces import member_card_services as services
from tests.l3_gap.helpers import event_card, live_event, png_bytes, programme, stage
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db


def _upload(api, url, consent=True, content_type="image/png"):
    presign = api.post(url, {"content_type": content_type}, format="json")
    assert presign.status_code == 201, presign.content
    key = presign.json()["object_key"]
    stage(key, png_bytes(), content_type)
    return api.put(url, {"object_key": key, "content_type": content_type, "holder_consented": consent},
                   format="json"), key


def test_staff_set_a_member_card_photo_and_it_resolves_the_open_request():
    space = card_space("gap-sp-member")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    api = client(sm)
    api.post(f"/api/v1/admin/member-cards/{card.pk}/photo-request", {"reason": "Blurry"}, format="json")
    response, key = _upload(api, f"/api/v1/admin/member-cards/{card.pk}/photo")
    assert response.status_code == 200, response.content
    card.refresh_from_db()
    assert card.photo_object_key == key and card.photo_consent_at is not None
    assert CardPhotoRequest.objects.get(member_card=card).resolved_at is not None
    assert AuditLog.objects.filter(action="card.photo_set_by_staff", meta__holder_kind="member_card").exists()


def test_the_holder_must_have_agreed():
    space = card_space("gap-sp-consent")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    response, _key = _upload(client(sm), f"/api/v1/admin/member-cards/{card.pk}/photo", consent=False)
    assert response.status_code == 400
    card.refresh_from_db()
    assert not card.photo_object_key


def test_the_final_key_is_never_client_chosen():
    space = card_space("gap-sp-key")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    other = card_space("gap-sp-key-2")
    response = client(sm).put(f"/api/v1/admin/member-cards/{card.pk}/photo",
                              {"object_key": f"member-cards/{other.pk}/abc", "holder_consented": True}, format="json")
    assert response.status_code == 400


def test_staff_without_card_authority_and_other_spaces_are_refused():
    space = card_space("gap-sp-authority")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    inventory = custom_staff(space, ["inventory_manager"], "gap-sp-inv")
    url = f"/api/v1/admin/member-cards/{card.pk}/photo"
    assert client(inventory).post(url, {"content_type": "image/png"}, format="json").status_code in (403, 404)
    stranger = manager(card_space("gap-sp-stranger"))
    assert client(stranger).post(url, {"content_type": "image/png"}, format="json").status_code == 404


def test_a_revoked_member_card_takes_no_photo():
    space = card_space("gap-sp-revoked")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    services.revoke_card(sm, card, note="Left the space")
    response = client(sm).post(f"/api/v1/admin/member-cards/{card.pk}/photo", {"content_type": "image/png"},
                               format="json")
    assert response.status_code == 400


def test_programme_managers_set_a_programme_card_photo():
    from apps.id_programmes import cards as programme_cards
    space, _org, sm, row = programme("gap-sp-prog")
    card = programme_cards.add(sm, row, name="Asha", email="asha@example.com")
    response, _key = _upload(client(sm), f"/api/v1/admin/id-programme-cards/{card.pk}/photo")
    assert response.status_code == 200, response.content
    card.refresh_from_db()
    assert card.photo_object_key.startswith(f"card-photos/{space.pk}/") and card.photo_content_type == "image/png"
    card.status = "rejected"
    card.save(update_fields=["status"])
    response = client(sm).post(f"/api/v1/admin/id-programme-cards/{card.pk}/photo", {"content_type": "image/png"},
                               format="json")
    assert response.status_code == 400


def test_event_organisers_set_an_event_card_photo_and_check_in_staff_cannot():
    space, event = live_event("gap-sp-event")
    sm = manager(space)
    _user, card = event_card(space, event)
    response, _key = _upload(client(sm), f"/api/v1/admin/event-id-cards/{card.pk}/photo")
    assert response.status_code == 200, response.content
    card.refresh_from_db()
    assert card.photo_object_key
    door = custom_staff(space, ["handover"], "gap-sp-door")
    refused = client(door).post(f"/api/v1/admin/event-id-cards/{card.pk}/photo", {"content_type": "image/png"},
                                format="json")
    assert refused.status_code in (403, 404)
