from urllib.parse import parse_qs, urlparse

import pytest

from apps.makerspaces.models import MakerspaceMembership
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payments.models import (
    MakerspacePaymentSettings,
    Payment,
    PlatformStripeConnectSettings,
    StripeConnectOAuthState,
)
from apps.payments.services import create_payment
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.payments.test_machine_payments import service_request
from tests.payments.account_helpers import make_payer
from tests.return_helpers import make_member, make_space, make_user


pytestmark = pytest.mark.django_db


def _platform_settings():
    platform = PlatformStripeConnectSettings.load()
    platform.set_stripe_secret_key("sk_platform")
    platform.set_stripe_webhook_secret("whsec_platform")
    platform.stripe_connect_client_id = "ca_platform"
    platform.save()
    return platform


def _oauth_state(settings, slug, *, platform_actor=False):
    settings.PLATFORM_DOMAIN_SUFFIX = ".managed.test"
    settings.PUBLIC_APP_BASE_URL = "https://app.managed.test"
    settings.STRIPE_CONNECT_REDIRECT_URI = (
        "https://api.managed.test/api/v1/payments/connect/callback"
    )
    _platform_settings()
    makerspace = make_space(slug)
    actor = (make_user(f"{slug}-platform", role=User.Role.SUPERADMIN) if platform_actor else
             make_member(f"{slug}-manager", makerspace))
    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(
        f"/api/v1/admin/makerspace/{makerspace.id}/payment-settings/connect/onboard",
        HTTP_HOST="localhost",
    )
    raw_state = parse_qs(urlparse(response.data["authorize_url"]).query)["state"][0]
    return makerspace, actor, raw_state


@pytest.mark.parametrize("revocation", ["suspended", "restricted", "inactive"])
def test_callback_rejects_actor_who_lost_account_authority(
    settings, monkeypatch, revocation
):
    makerspace, actor, raw_state = _oauth_state(
        settings, f"oauth-actor-{revocation}"
    )
    if revocation == "inactive":
        actor.is_active = False
        actor.save(update_fields=["is_active"])
    else:
        actor.access_status = getattr(User.AccessStatus, revocation.upper())
        actor.save(update_fields=["access_status"])
    exchanges = []
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda code: exchanges.append(code),
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_revoked"},
        HTTP_HOST="localhost",
    )

    assert response.status_code == 302
    assert response["Location"] == (
        "https://app.managed.test/admin/settings/money?stripe_connect=failed"
    )
    assert makerspace.slug not in response["Location"]
    assert exchanges == []


def test_callback_rejects_space_that_is_no_longer_authorized(settings, monkeypatch):
    makerspace, _actor, raw_state = _oauth_state(settings, "oauth-space-archived")
    makerspace.archived_at = timezone.now()
    makerspace.save(update_fields=["archived_at"])
    exchanges = []
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda code: exchanges.append(code),
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_revoked"},
        HTTP_HOST="localhost",
    )

    assert response["Location"] == (
        "https://app.managed.test/admin/settings/money?stripe_connect=failed"
    )
    assert makerspace.slug not in response["Location"]
    assert exchanges == []
    assert StripeConnectOAuthState.objects.get(makerspace=makerspace).consumed_at
    assert not MakerspacePaymentSettings.objects.filter(makerspace=makerspace).exists()


def test_callback_rejects_actor_after_manage_action_is_removed(settings, monkeypatch):
    makerspace, actor, raw_state = _oauth_state(settings, "oauth-action-revoked")
    # Demote the Space Manager to Inventory Manager: still staff, no manage_makerspace.
    assign_builtin_roles(actor, makerspace, "inventory_manager")
    exchanges = []
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda code: exchanges.append(code),
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_revoked"},
        HTTP_HOST="localhost",
    )

    assert response["Location"].endswith("/admin/settings/money?stripe_connect=failed")
    assert makerspace.slug not in response["Location"]
    assert exchanges == []


def test_callback_rejects_actor_after_membership_is_revoked(settings, monkeypatch):
    makerspace, actor, raw_state = _oauth_state(settings, "oauth-membership-revoked")
    MakerspaceMembership.staff_tracks.filter(user=actor, makerspace=makerspace).update(status="revoked")
    exchanges = []
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda code: exchanges.append(code),
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_revoked"},
        HTTP_HOST="localhost",
    )

    assert response["Location"] == (
        "https://app.managed.test/admin/settings/money?stripe_connect=failed"
    )
    assert makerspace.slug not in response["Location"]
    assert exchanges == []
    assert not MakerspacePaymentSettings.objects.filter(makerspace=makerspace).exists()


def test_callback_rechecks_authority_after_remote_exchange(settings, monkeypatch):
    makerspace, actor, raw_state = _oauth_state(
        settings, "oauth-membership-revoked-during-exchange"
    )

    def exchange(_code):
        MakerspaceMembership.staff_tracks.filter(user=actor, makerspace=makerspace).update(
            status="revoked"
        )
        return "acct_laterevocation"

    monkeypatch.setattr("apps.payments_rail.views_connect.exchange_oauth_code", exchange)
    revoked = []
    monkeypatch.setattr(
        "apps.payments.connect.deauthorize_account",
        lambda account_id: revoked.append(account_id),
    )
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.fetch_account",
        lambda account_id: {
            "id": account_id,
            "charges_enabled": True,
            "payouts_enabled": True,
            "details_submitted": True,
        },
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_late_revocation"},
        HTTP_HOST="localhost",
    )

    assert response["Location"] == (
        "https://app.managed.test/admin/settings/money?stripe_connect=failed"
    )
    assert makerspace.slug not in response["Location"]
    assert revoked == ["acct_laterevocation"]
    assert not MakerspacePaymentSettings.objects.filter(makerspace=makerspace).exists()


def test_callback_cannot_replace_account_with_pending_payments(settings, monkeypatch):
    makerspace, actor, raw_state = _oauth_state(settings, "oauth-pending-drain")
    MakerspacePaymentSettings.objects.create(
        makerspace=makerspace,
        connect_account_id="acct_pending",
        connect_status=MakerspacePaymentSettings.ConnectStatus.ACTIVE,
        connect_charges_enabled=True,
    )
    payer = make_payer("oauth-pending-payer", makerspace)
    create_payment(
        makerspace=makerspace,
        subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST,
        subject_id=service_request(makerspace, payer).id,
        member=payer,
        amount="10.00",
        currency="usd",
        created_by=actor,
    )
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda _code: "acct_replacement",
    )
    fetched = []
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.fetch_account",
        lambda account_id: fetched.append(account_id),
    )
    revoked = []
    monkeypatch.setattr(
        "apps.payments.connect.deauthorize_account", revoked.append
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_replacement"},
        HTTP_HOST="localhost",
    )

    merchant = MakerspacePaymentSettings.objects.get(makerspace=makerspace)
    assert response["Location"].endswith("stripe_connect=failed")
    assert merchant.connect_account_id == "acct_pending"
    assert fetched == []
    assert revoked == ["acct_replacement"]


def test_callback_redirects_verified_domain_to_single_tenant_staff_path(
    settings, monkeypatch
):
    makerspace, _, raw_state = _oauth_state(settings, "oauth-verified-domain")
    makerspace.frontend_domain = "verified-space.example"
    makerspace.frontend_domain_status = makerspace.DomainStatus.VERIFIED
    makerspace.save(update_fields=["frontend_domain", "frontend_domain_status"])
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.exchange_oauth_code",
        lambda _code: "acct_verifieddomain",
    )
    monkeypatch.setattr(
        "apps.payments_rail.views_connect.fetch_account",
        lambda account_id: {
            "id": account_id,
            "charges_enabled": True,
            "payouts_enabled": True,
            "details_submitted": True,
        },
    )

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": raw_state, "code": "ac_verified_domain"},
        HTTP_HOST="localhost",
    )

    assert response["Location"] == (
        "https://verified-space.example/admin/settings/money?stripe_connect=success"
    )


def test_connect_callback_is_not_available_in_self_host_mode(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.PUBLIC_APP_BASE_URL = "http://localhost:5000"

    response = APIClient().get(
        "/api/v1/payments/connect/callback",
        {"state": "irrelevant", "code": "ac_irrelevant"},
        HTTP_HOST="localhost",
    )

    assert response.status_code == 404
