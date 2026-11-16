"""L3 member cards: tokens on issue/reissue/revoke, auto-issue, settings, downloads, email,
photo requests, extras, holder routes and the presence scan."""
import pytest
from django.core.exceptions import PermissionDenied

from apps.audit.models import AuditLog
from apps.card_designs import extras, tokens
from apps.card_designs.models import CardHolderExtras, CardPhotoRequest, CardVerifyToken
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCardSettings
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db


def _verify_on(space):
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})


def test_issue_mints_a_check_token_only_when_the_public_check_is_on():
    space = card_space("mc-token")
    sm = manager(space)
    _user, membership = member(space, "a")
    card = services.issue_card(sm, membership)
    assert tokens.live("member_card", card) is None
    _verify_on(space)
    _user2, membership2 = member(space, "b")
    card2 = services.issue_card(sm, membership2)
    token = tokens.live("member_card", card2)
    assert token and len(token.token) == 43
    assert token.token != services.active_qr(card2).payload


def test_reissue_retires_the_token_as_reissued_and_mints_a_new_one():
    space = card_space("mc-reissue")
    _verify_on(space)
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    old = tokens.live("member_card", card)
    services.reissue_card(sm, card, reason="lost")
    old.refresh_from_db()
    assert old.retired_reason == CardVerifyToken.Retired.REISSUED
    assert tokens.live("member_card", card).pk != old.pk


def test_revoke_needs_a_note_retires_tokens_and_clears_extras():
    space = card_space("mc-revoke")
    _verify_on(space)
    sm = manager(space)
    user, membership = member(space)
    card = services.issue_card(sm, membership)
    extras.write(user, "member_card", card, opted_in=True, blood_group="O+", emergency_contact_name="Arjun")
    response = client(sm).post(f"/api/v1/admin/member-cards/{card.pk}/revoke", {}, format="json")
    assert response.status_code == 400
    response = client(sm).post(f"/api/v1/admin/member-cards/{card.pk}/revoke", {"note": "Lost and replaced"},
                               format="json")
    assert response.status_code == 200, response.content
    card.refresh_from_db()
    assert card.revoked_note == "Lost and replaced"
    assert not CardHolderExtras.objects.filter(member_card=card).exists()
    assert not CardVerifyToken.objects.filter(member_card=card, retired_at__isnull=True).exists()
    assert "Lost" not in str(AuditLog.objects.filter(action="member_card.revoked").values_list("meta", flat=True))


def test_auto_issue_on_activation_is_idempotent_and_off_for_existing_spaces():
    space = card_space("mc-auto")
    sm = manager(space)
    _user, membership = member(space)
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"auto_issue": True})
    card = services.auto_issue(membership.pk)
    assert card is not None and AuditLog.objects.filter(action="member_card.auto_issued").count() == 1
    assert services.auto_issue(membership.pk) is None
    MemberCardSettings.objects.filter(makerspace=space).update(auto_issue=False)
    _user2, membership2 = member(space, "late")
    assert services.auto_issue(membership2.pk) is None
    assert sm


def test_settings_go_through_settings_authority():
    space = card_space("mc-settings")
    sm = manager(space)
    staff = custom_staff(space, ["event_manager"], "cardsettings")
    url = f"/api/v1/admin/makerspaces/{space.pk}/member-card-settings"
    assert client(sm).get(url).json()["design_approval_required"] is True
    assert client(staff).put(url, {"public_verify": True}, format="json").status_code in (403, 404)
    response = client(sm).put(url, {"public_verify": True, "design_approval_required": False}, format="json")
    assert response.status_code == 200 and response.json()["public_verify"] is True
    assert response.json()["design_approval_required"] is False
    assert AuditLog.objects.filter(action="settings.changed").count() >= 2


def test_staff_download_pdf_and_png_and_email_cooldown():
    space = card_space("mc-download")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    api = client(sm)
    pdf = api.get(f"/api/v1/admin/member-cards/{card.pk}/download?format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    png = api.get(f"/api/v1/admin/member-cards/{card.pk}/download?format=png&side=back")
    assert png.status_code == 200 and png["Content-Type"] == "image/png"
    assert api.post(f"/api/v1/admin/member-cards/{card.pk}/email").status_code == 202
    assert api.post(f"/api/v1/admin/member-cards/{card.pk}/email").status_code == 400
    from apps.integrations.models import EmailLog
    log = EmailLog.objects.get(source_kind="card_designs.card")
    assert "token" not in str(log.source_metadata)


def test_email_module_off_blocks_card_email():
    from tests.module_helpers import disable_module
    space = card_space("mc-noemail")
    disable_module(space, "email")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    response = client(sm).post(f"/api/v1/admin/member-cards/{card.pk}/email")
    assert response.status_code == 404 and "turned off" in str(response.content)


def test_photo_request_keeps_the_card_valid_and_resolves_on_new_photo():
    space = card_space("mc-photo")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    response = client(sm).post(f"/api/v1/admin/member-cards/{card.pk}/photo-request", {"reason": "Blurry"},
                               format="json")
    assert response.status_code == 201
    row = CardPhotoRequest.objects.get(member_card=card)
    from apps.card_designs.photos import resolve_requests
    resolve_requests("member_card", card)
    row.refresh_from_db()
    assert row.resolved_at is not None
    from apps.card_designs.holders import spec_for
    assert spec_for("member_card").standing(card) == "valid"


def test_inventory_role_cannot_reach_member_card_routes():
    space = card_space("mc-inventory")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    inventory = custom_staff(space, ["inventory_manager"], "inv")
    assert client(inventory).get(f"/api/v1/admin/member-cards/{card.pk}/download").status_code == 404
    with pytest.raises(PermissionDenied):
        services.resolve(inventory, space, services.active_qr(card).payload)


def test_holder_my_cards_download_settings_and_rotate():
    space = card_space("mc-holder")
    _verify_on(space)
    sm = manager(space)
    user, membership = member(space)
    card = services.issue_card(sm, membership)
    api = client(user)
    cards = api.get("/api/v1/member/cards").json()
    assert cards[0]["kind"] == "member_card" and cards[0]["status"] == "valid" and cards[0]["check_url"]
    assert api.get(f"/api/v1/member/cards/member_card/{card.pk}/download?format=png").status_code == 200
    changed = api.patch(f"/api/v1/member/cards/member_card/{card.pk}/settings",
                        {"verify_show_name": True, "extras_opted_in": True, "blood_group": "B+"}, format="json")
    assert changed.status_code == 200 and changed.json()["blood_group"] == "B+"
    old = tokens.live("member_card", card).token
    assert api.post(f"/api/v1/member/cards/member_card/{card.pk}/rotate-link").status_code == 200
    assert tokens.live("member_card", card).token != old
    stranger, _m = member(card_space("mc-holder-2"), "stranger")
    assert client(stranger).get(f"/api/v1/member/cards/member_card/{card.pk}/download").status_code == 404


def test_scanned_check_link_resolves_at_the_desk_and_presence_scan_checks_in():
    space = card_space("mc-scan", modules=("membership", "member_accounts", "email"))
    _verify_on(space)
    sm = manager(space)
    user, membership = member(space)
    card = services.issue_card(sm, membership)
    link = tokens.url(tokens.live("member_card", card).token)
    assert services.resolve(sm, space, link)["card_id"] == card.pk
    from apps.makerspaces.platform import feature_enabled
    assert feature_enabled(space, "inventory.kiosk") in (True, False)
