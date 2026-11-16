"""Decision 329 (a): with `*.wallet_passes` off, existing passes hear only that they ended.

No new pass is issued and no other content reaches a pass; a voided, revoked or expired card still
updates its pass (Apple push / Google PATCH, the PassKit web service and the refresh sweep), so a
revoked card never looks valid in someone's wallet.
"""
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.card_designs.models import WalletPass
from apps.card_designs.wallet import service
from apps.card_designs.wallet.credentials import auth_token, digest
from apps.makerspaces import member_card_services as cards
from tests.l3_local.helpers import card_space, manager, member

pytestmark = pytest.mark.django_db
WALLET = "membership.wallet_passes"


@pytest.fixture
def pushes(monkeypatch):
    sent = []
    monkeypatch.setattr("apps.card_designs.wallet.apple_push.notify", lambda row: sent.append(row.pk) or 1)
    return sent


def _case(slug, *, wallet_on):
    space = card_space(slug, features=(WALLET,) if wallet_on else ())
    sm = manager(space)
    card = cards.issue_card(sm, member(space)[1])
    serial = f"{slug}-serial"
    row = WalletPass.objects.create(makerspace=space, member_card=card, platform="apple", serial=serial,
                                    auth_token_digest=digest(auth_token(serial)), content_digest="stale")
    return space, sm, card, row


def _ended(monkeypatch, standing):
    real = service.pass_content
    monkeypatch.setattr(service, "pass_content", lambda kind, card: {**real(kind, card), "standing": standing})


def test_switched_off_no_content_change_reaches_a_live_pass(pushes):
    _space, _sm, card, row = _case("w329-off-live", wallet_on=False)

    assert service.refresh("member_card", card) == 0
    assert service.sweep_changed(limit=50) == 0

    row.refresh_from_db()
    assert pushes == [] and row.generation == 1 and row.content_digest == "stale"


def test_switched_on_content_changes_still_reach_the_pass(pushes):
    _space, _sm, card, row = _case("w329-on", wallet_on=True)

    assert service.refresh("member_card", card) == 1
    assert pushes == [row.pk]


def test_switched_off_a_revoked_card_still_voids_its_pass(pushes):
    _space, sm, card, row = _case("w329-off-revoked", wallet_on=False)
    cards.revoke_card(sm, card)
    WalletPass.objects.filter(pk=row.pk).update(voided_at=timezone.now())

    assert service.refresh("member_card", card) == 1
    assert pushes == [row.pk]


@pytest.mark.parametrize("standing", ["expired", "revoked"])
def test_switched_off_the_sweep_still_sends_an_ending(standing, pushes, monkeypatch):
    _space, _sm, _card, row = _case(f"w329-off-{standing}", wallet_on=False)
    _ended(monkeypatch, standing)

    assert service.sweep_changed(limit=50) == 1
    assert pushes == [row.pk]


def test_switched_off_no_new_pass_is_issued(monkeypatch):
    _space, _sm, card, _row = _case("w329-off-issue", wallet_on=False)
    monkeypatch.setattr("apps.card_designs.wallet.service.configured_platforms", lambda *a: ("apple",))
    monkeypatch.setattr("apps.card_designs.wallet.credentials.configured_platforms", lambda *a: ("apple",))

    with pytest.raises(ValidationError):
        service.request_pass(card.membership.user, "member_card", card, "apple")


def _latest(row, monkeypatch):
    monkeypatch.setattr("apps.card_designs.wallet.views_apple.apple_for",
                        lambda space_id: SimpleNamespace(pass_type_id="pass.test"))
    monkeypatch.setattr("apps.card_designs.wallet.apple.build_pkpass", lambda row, content: b"PKPASS")
    return APIClient().get(f"/api/v1/wallet/apple/v1/passes/pass.test/{row.serial}",
                           HTTP_AUTHORIZATION=f"ApplePass {auth_token(row.serial)}")


def test_the_web_service_keeps_a_live_pass_unchanged_while_switched_off(monkeypatch):
    _space, _sm, _card, row = _case("w329-ws-live", wallet_on=False)
    assert _latest(row, monkeypatch).status_code == 304


def test_the_web_service_serves_the_ending_while_switched_off(monkeypatch):
    _space, sm, card, row = _case("w329-ws-revoked", wallet_on=False)
    cards.revoke_card(sm, card)
    response = _latest(row, monkeypatch)
    assert response.status_code == 200 and response.content == b"PKPASS"
