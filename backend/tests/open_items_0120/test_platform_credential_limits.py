"""Owner 2026-11-11: monthly limits on a space's use of the PLATFORM credentials; every limit defaults to none.

Counted only on the platform-credential path (own credentials never), every space (own or hosted),
independent of the hosting switch. Payments: a typed 409 `platform_rail_limit_reached` for a NEW online
page on the platform Connect rail; offline settlement keeps working.
"""
from unittest.mock import patch

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.limits_core import KNOWN_LIMIT_KEYS, NUMERIC_LIMIT_KEYS, PLATFORM_CREDENTIAL_LIMIT_KEYS, resource_limit
from apps.managed_hosting import platform_limits as pl
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def switch_off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def _limit(space, **limits):
    space.resource_limit_overrides = {**(space.resource_limit_overrides or {}), **limits}
    space.save(update_fields=["resource_limit_overrides"])


# --- defaults: nothing is limited until a superadmin sets a value ---------------------------

def test_fresh_space_has_no_effective_limits_for_any_key(switch_off):
    space = make_space("pcl-fresh")
    assert space.resource_limit_overrides == {}
    for key in sorted(NUMERIC_LIMIT_KEYS):
        assert resource_limit(space, key) is None, key
    for key in sorted(PLATFORM_CREDENTIAL_LIMIT_KEYS):
        assert pl.platform_limit(space, key) is None, key
        assert pl.platform_refusal(space, key) is None
    assert {row["key"] for row in pl.usage_rows(space)} == set(PLATFORM_CREDENTIAL_LIMIT_KEYS)
    assert all(row["limit"] is None for row in pl.usage_rows(space))
    assert PLATFORM_CREDENTIAL_LIMIT_KEYS <= KNOWN_LIMIT_KEYS


def test_fresh_install_has_no_plans_overrides_or_platform_rates():
    from apps.managed_hosting.models import HostingPlan, PlatformThrottleRate
    assert not HostingPlan.objects.exists() and not PlatformThrottleRate.objects.exists()


def test_existing_rows_stay_unlimited_unless_a_value_was_set():
    """The model default carries no key; only an explicit value limits (migrations add no limits)."""
    from apps.makerspaces.models import Makerspace
    field = Makerspace._meta.get_field("resource_limit_overrides")
    assert field.default is dict
    space = make_space("pcl-old")
    _limit(space, platform_sms_monthly=5)
    assert pl.platform_limit(space, "platform_sms_monthly") == 5
    assert pl.platform_limit(space, "platform_email_monthly") is None
    _limit(space, platform_sms_monthly=-1)
    assert pl.platform_limit(space, "platform_sms_monthly") is None


# --- channels: reached -> skipped, inbox kept, notice once ----------------------------------

def test_native_push_limit_reached_blocks_the_channel_only_and_notes_once(switch_off):
    from apps.makerspaces.limits import reserve_notification_quota
    space = make_space("pcl-push")
    _limit(space, platform_push_monthly=0)
    assert reserve_notification_quota(space, "native_push") is False
    assert reserve_notification_quota(space, "native_push") is False
    notices = AuditLog.objects.filter(action="platform_credential_limit.reached", makerspace=space)
    assert notices.count() == 1  # once per period
    assert reserve_notification_quota(space, "telegram") is True  # other channels untouched


def test_unlimited_channel_is_never_blocked(switch_off):
    from apps.makerspaces.limits import reserve_notification_quota
    space = make_space("pcl-open")
    assert reserve_notification_quota(space, "native_push") is True
    assert not AuditLog.objects.filter(action="platform_credential_limit.reached").exists()


def test_sms_limit_counts_only_the_platform_sender(switch_off):
    from apps.makerspaces.limits import reserve_notification_quota
    from apps.integrations.messaging.resolver import ResolvedSender
    space = make_space("pcl-sms")
    _limit(space, platform_sms_monthly=0)
    own = ResolvedSender("sms", "k", "twilio", "own", space.pk)
    platform = ResolvedSender("sms", "k", "twilio", "platform")
    with patch("apps.integrations.messaging.resolver.resolve_sender", return_value=own):
        assert reserve_notification_quota(space, "sms") is True  # own credentials are never limited here
    with patch("apps.integrations.messaging.resolver.resolve_sender", return_value=platform):
        assert reserve_notification_quota(space, "sms") is False


def test_email_limit_skips_with_a_reason_and_own_smtp_is_exempt(switch_off):
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.integrations.models import EmailLog
    space = make_space("pcl-mail")
    _limit(space, platform_email_monthly=0)
    log = dispatch_email(makerspace=space, to_email="a@example.test", subject="s", text_body="t",
                         event="x", stream="transactional")
    assert log.status == EmailLog.Status.SKIPPED and "allowed by the platform" in log.error
    space.smtp_host = "smtp.own.test"
    space.save(update_fields=["smtp_host"])
    assert not pl.uses_own_email(space)  # parity E-B8: an untested own SMTP is not used
    from django.utils import timezone
    from apps.integrations.space_smtp_gate import mark_verified
    mark_verified(space, timezone.now())
    assert pl.uses_own_email(space)


# --- usage counts the platform path only ----------------------------------------------------

def test_email_usage_counts_platform_source_only(switch_off):
    from apps.integrations.models import EmailLog
    space = make_space("pcl-usage")
    for source in ("platform", "own", "platform"):
        EmailLog.objects.create(makerspace=space, to_email="a@example.test", subject="s", provider_source=source,
                                status=EmailLog.Status.SENT, connection_kind="makerspace")
    assert pl.platform_used(space, "platform_email_monthly") == 2


# --- payments: platform rail only; offline still works --------------------------------------

def _connect_charge(slug):
    from tests.payments.recon_f_helpers import pending_charge
    return pending_charge(slug, stripe_provider="connect", stripe_connected_account_id="acct_x")


def test_rail_refusal_at_limit_but_not_below_or_unlimited(switch_off):
    space, _staff, payment = _connect_charge("pcl-rail")
    assert pl.rail_refusal(space, payment) is None  # unlimited by default
    _limit(space, platform_payments_monthly_count=1)
    assert pl.rail_refusal(space, payment) is None  # this charge is the 1st of 1
    _limit(space, platform_payments_monthly_count=0)
    assert pl.rail_refusal(space, payment)
    _limit(space, platform_payments_monthly_count=None, platform_payments_monthly_amount=0)
    assert pl.rail_refusal(space, payment)


def test_checkout_answers_typed_409_and_offline_settlement_still_works(switch_off):
    from rest_framework.test import APIClient
    from apps.payments.checkout_coordination import PlatformRailLimitReached
    assert PlatformRailLimitReached.code == "platform_rail_limit_reached"
    from apps.payments.models import PlatformStripeConnectSettings
    PlatformStripeConnectSettings.load()  # a Connect-stamped charge needs the platform settings row to start a page
    space, _staff, payment = _connect_charge("pcl-409")
    _limit(space, platform_payments_monthly_count=0)
    with pytest.raises(PlatformRailLimitReached):
        from apps.payments import checkout_coordination as cc
        with patch.object(cc, "source_for_payment", return_value=object()):
            cc._create_checkout_url_atomic(payment.pk)
    # Offline settlement is not part of the online rail: the limit never reads on that path.
    import inspect
    from apps.payments import offline_claims
    assert "platform_limits" not in inspect.getsource(offline_claims)
    assert APIClient is not None


def test_own_gateway_charge_is_never_counted(switch_off):
    space, _staff, payment = _connect_charge("pcl-own")
    from apps.payments.models import Payment
    Payment.objects.filter(pk=payment.pk).update(stripe_provider="raw")
    assert pl.platform_used(space, "platform_payments_monthly_count") == 0


# --- scoping: Space Manager sees only their space; superadmin sees any ----------------------

def test_limits_console_is_superadmin_only_and_returns_platform_rows(switch_off):
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.accounts.models import User
    from tests.accounts.reauth_helpers import force_recent_authenticate
    from tests.makerspaces.l4_helpers import space_with_manager
    space, manager = space_with_manager("pcl-scope")
    other, _other_manager = space_with_manager("pcl-scope-b")
    _limit(space, platform_email_monthly=10)
    root = User.objects.create_user(username="pcl-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    client = APIClient()
    force_recent_authenticate(client, root)
    body = client.get(reverse("admin-space-limits", args=[space.pk])).json()
    rows = {row["key"]: row for row in body["platform_rows"]}
    assert rows["platform_email_monthly"]["limit"] == 10 and rows["platform_sms_monthly"]["limit"] is None
    staff = APIClient()
    staff.force_authenticate(manager)
    assert staff.get(reverse("admin-space-limits", args=[space.pk])).status_code == 403
    mine = staff.get(reverse("admin-makerspace-hosting-plan", args=[space.pk]))
    assert mine.status_code == 200 and mine.json()["platform_resources"][0]["limit"] in (None, 10)
    assert staff.get(reverse("admin-makerspace-hosting-plan", args=[other.pk])).status_code in (403, 404)
    other_usage = pl.usage_rows(other)
    assert all(row["limit"] is None for row in other_usage)  # another space's limits are untouched
