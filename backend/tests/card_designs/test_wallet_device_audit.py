"""Apple pass web service: device register / unregister go through an audited wallet service (Codex arch-1).

Registering, refreshing the push token and unregistering each leave one audit entry naming the pass and the
platform only (never the device identifier or the push token). A wrong token changes nothing and audits nothing.
"""
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.card_designs.models import WalletDeviceRegistration, WalletPass
from apps.card_designs.wallet.credentials import auth_token, digest
from apps.makerspaces import member_card_services as cards
from tests.l3_local.helpers import card_space, manager, member

pytestmark = pytest.mark.django_db
DEVICE = "device-library-id-1"


@pytest.fixture
def row(monkeypatch):
    monkeypatch.setattr("apps.card_designs.wallet.views_apple.apple_for",
                        lambda space_id: SimpleNamespace(pass_type_id="pass.test"))
    space = card_space("wallet-dev-audit", features=("membership.wallet_passes",))
    card = cards.issue_card(manager(space), member(space)[1])
    serial = "wallet-dev-audit-serial"
    return WalletPass.objects.create(makerspace=space, member_card=card, platform="apple", serial=serial,
                                     auth_token_digest=digest(auth_token(serial)), content_digest="x")


def _url(row):
    return f"/api/v1/wallet/apple/v1/devices/{DEVICE}/registrations/pass.test/{row.serial}"


def _call(row, method, token=None, **body):
    client = APIClient()
    header = f"ApplePass {token or auth_token(row.serial)}"
    return getattr(client, method)(_url(row), body or None, format="json", HTTP_AUTHORIZATION=header)


def _audits(action):
    return list(AuditLog.objects.filter(action=action).order_by("pk"))


def test_register_refresh_and_unregister_are_each_audited(row):
    assert _call(row, "post", pushToken="tok-1").status_code == 201
    assert _call(row, "post", pushToken="tok-1").status_code == 200  # unchanged: no second entry
    assert _call(row, "post", pushToken="tok-2").status_code == 200  # token refreshed: audited
    registered = _audits("wallet_pass.device_registered")
    assert [entry.meta["created"] for entry in registered] == [True, False]
    assert WalletDeviceRegistration.objects.get(wallet_pass=row).push_token == "tok-2"
    assert _call(row, "delete").status_code == 200
    assert _call(row, "delete").status_code == 200  # already gone: nothing to audit
    assert len(_audits("wallet_pass.device_unregistered")) == 1
    assert not WalletDeviceRegistration.objects.filter(wallet_pass=row).exists()


def test_the_audit_never_holds_the_device_id_or_push_token(row):
    _call(row, "post", pushToken="secret-push-token")
    entry = _audits("wallet_pass.device_registered")[0]
    text = str(entry.meta)
    assert DEVICE not in text and digest(DEVICE) not in text and "secret-push-token" not in text
    assert entry.meta["pass_id"] == row.pk and entry.meta["platform"] == "apple"
    assert entry.makerspace_id == row.makerspace_id and entry.actor_id is None


def test_a_wrong_token_changes_and_audits_nothing(row):
    assert _call(row, "post", token="not-the-token", pushToken="x").status_code == 401
    assert _call(row, "delete", token="not-the-token").status_code == 401
    assert not WalletDeviceRegistration.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="wallet_pass.device_").exists()
