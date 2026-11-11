"""P27 / P28 and the holder card row: the printed-card face for the browser, the card fonts it
uses, the verify footnote's time zone, and the photo facts the crop and clean-up steps need."""
import pytest

from apps.card_designs import extras, tokens
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCardSettings
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _card(slug, *, verify=False):
    space = card_space(slug)
    if verify:
        MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    sm = manager(space)
    user, membership = member(space)
    return space, sm, user, services.issue_card(sm, membership)


def test_face_returns_the_published_document_values_and_inline_qr():
    _space, _sm, user, card = _card("gap-fv-face", verify=True)
    response = client(user).get(f"/api/v1/member/cards/member_card/{card.pk}/face")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["document"]["version"] == 2 and body["document"]["front"]["layers"]
    assert body["values"]["number"] and body["values"]["name"]
    assert body["desk_qr"].startswith("data:image/svg+xml") and body["verify_qr"].startswith("data:image/svg+xml")
    assert response["Cache-Control"] == "private, no-store"


def test_face_hides_the_extras_unless_the_holder_opted_in():
    _space, _sm, user, card = _card("gap-fv-extras")
    url = f"/api/v1/member/cards/member_card/{card.pk}/face"
    extras.write(user, "member_card", card, opted_in=False, blood_group="O+")
    assert "blood_group" not in client(user).get(url).json()["values"]
    extras.write(user, "member_card", card, opted_in=True, blood_group="O+", emergency_contact_name="Ravi",
                 emergency_contact_phone="98765")
    assert client(user).get(url).json()["values"]["blood_group"] == "O+"


def test_face_is_the_holders_alone_and_never_for_a_revoked_card():
    space, sm, user, card = _card("gap-fv-owner")
    stranger, _m = member(card_space("gap-fv-stranger"), "gap-fv-other")
    assert client(stranger).get(f"/api/v1/member/cards/member_card/{card.pk}/face").status_code == 404
    services.revoke_card(sm, card, note="Lost")
    assert client(user).get(f"/api/v1/member/cards/member_card/{card.pk}/face").status_code in (403, 404)


def test_font_route_serves_only_families_the_design_uses():
    _space, _sm, user, card = _card("gap-fv-font")
    url = f"/api/v1/member/cards/member_card/{card.pk}/fonts/comic-neue/400"
    assert client(user).get(url).status_code == 404


def test_my_cards_row_carries_photo_facts_for_crop_and_clean_up():
    _space, _sm, user, card = _card("gap-fv-row")
    row = client(user).get("/api/v1/member/cards").json()[0]
    assert row["photo_set"] is False and isinstance(row["photo_cleanup_available"], bool)
    assert 0.3 < row["photo_aspect"] < 3


def test_verify_answer_names_the_issuers_time_zone():
    space, _sm, _user, card = _card("gap-fv-verify", verify=True)
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    token = tokens.live("member_card", card).token
    body = client(manager(space, "gap-fv-checker")).get(f"/api/v1/public/card-verifications/{token}").json()
    assert body["timezone"] == "Asia/Kolkata" and body["status"] == "valid"
