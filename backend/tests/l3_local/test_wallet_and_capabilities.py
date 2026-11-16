"""L3 wallet passes (#132, Q-I11) and the capability table (X-3)."""
import pytest

from apps.card_designs import extras
from apps.card_designs.models import WalletPass
from apps.card_designs.wallet.content import pass_content
from apps.card_designs.wallet.credentials import auth_token, configured_platforms, digest
from apps.makerspaces import member_card_services as services
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def test_pass_content_never_carries_a_photo_or_the_extras():
    space = card_space("wp-content")
    sm = manager(space)
    user, membership = member(space)
    card = services.issue_card(sm, membership)
    extras.write(user, "member_card", card, opted_in=True, blood_group="AB-")
    content = pass_content("member_card", card)
    assert content["qr"] == services.active_qr(card).payload
    assert "AB-" not in str(content) and "photo" not in str(content).lower()


def test_wallet_buttons_hidden_without_platform_credentials():
    space = card_space("wp-hidden", features=("membership.wallet_passes",))
    sm = manager(space)
    user, membership = member(space)
    card = services.issue_card(sm, membership)
    assert configured_platforms() == ()
    rows = client(user).get("/api/v1/member/cards").json()
    assert rows[0]["wallet_platforms"] == []
    response = client(user).post(f"/api/v1/member/cards/member_card/{card.pk}/wallet/apple")
    assert response.status_code == 400


def test_apple_web_service_refuses_without_the_pass_token(settings):
    space = card_space("wp-apple")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    row = WalletPass.objects.create(makerspace=space, member_card=card, platform="apple", serial="abc123",
                                    auth_token_digest=digest(auth_token("abc123")))
    from rest_framework.test import APIClient
    response = APIClient().get("/api/v1/wallet/apple/v1/passes/pass.test/abc123")
    assert response.status_code == 401
    assert row.pk


def test_capability_definitions_and_defaults():
    from apps.makerspaces.capability_definitions import FEATURES
    for key, parent in (("membership.id_programmes", "membership"), ("membership.wallet_passes", "membership"),
                        ("events.id_cards", "events"), ("events.ticket_designs", "events"),
                        ("events.wallet_passes", "events")):
        assert FEATURES[key].parent_module == parent and FEATURES[key].default_enabled is False
    assert FEATURES["events.wallet_passes"].requires_features == ("events.id_cards",)


def test_rbac_actions_and_space_manager_implications():
    from apps.accounts import rbac
    space = card_space("wp-rbac")
    sm = manager(space)
    for action in (rbac.Action.MANAGE_ID_PROGRAMMES, rbac.Action.VIEW_ID_PROGRAMMES,
                   rbac.Action.APPROVE_CARD_DESIGNS):
        assert rbac.can(sm, action, space.pk)
    assert rbac.Action.APPROVE_CARD_DESIGNS in rbac.ROLE_GRANTABLE_ACTIONS
