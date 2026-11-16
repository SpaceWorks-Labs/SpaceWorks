"""Decision 281 follow-ups: the per-space platform-fallback switch, defaults, queued counting and the notice."""
import pytest

from apps.audit.models import AuditLog
from apps.integrations.models import ChannelConfiguration, EmailLog
from apps.managed_hosting import platform_limits as pl
from apps.managed_hosting.platform_switch import CHANNELS, platform_allowed, platform_switches
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def switch_off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def test_new_space_defaults_on_for_all_five():
    space = make_space("pcb-defaults")
    assert set(CHANNELS) == {"email", "sms", "whatsapp", "native_push", "wallet"}
    assert platform_switches(space) == {channel: True for channel in CHANNELS}
    for channel in ("sms", "whatsapp", "email", "native_push"):
        provider = "twilio" if channel in ("sms", "whatsapp") else "builtin"
        row = ChannelConfiguration.objects.create(makerspace=space, channel=channel, provider=provider)
        assert row.use_platform_sender is True  # model default is now True for NEW rows


def test_existing_explicit_sms_opt_out_is_kept_and_enforced():
    space = make_space("pcb-optout")
    ChannelConfiguration.objects.create(makerspace=space, channel="sms", provider="twilio", use_platform_sender=False)
    assert platform_allowed(space, "sms") is False
    assert platform_allowed(space, "email") is True  # other channels untouched


@pytest.mark.parametrize("channel", ["email", "native_push"])
def test_switch_off_is_read_back_for_email_and_push(channel, switch_off):
    space = make_space(f"pcb-{channel}")
    ChannelConfiguration.objects.create(makerspace=space, channel=channel, provider="builtin",
                                        use_platform_sender=False)
    assert platform_allowed(space, channel) is False


def test_email_switch_off_skips_with_a_reason_and_own_account_is_exempt(switch_off):
    from apps.integrations.dispatch import dispatch_email
    space = make_space("pcb-mail-off")
    ChannelConfiguration.objects.create(makerspace=space, channel="email", provider="builtin",
                                        use_platform_sender=False)
    log = dispatch_email(makerspace=space, to_email="a@example.test", subject="s", text_body="t",
                         event="x", stream="transactional")
    assert log.status == EmailLog.Status.SKIPPED and log.error == "platform_email_disabled"
    space.smtp_host = "smtp.own.test"
    space.save(update_fields=["smtp_host"])
    assert not pl.uses_own_email(space)  # parity E-B8: an untested own SMTP is not used
    from django.utils import timezone
    from apps.integrations.space_smtp_gate import mark_verified
    mark_verified(space, timezone.now())
    assert pl.uses_own_email(space)  # own account: the switch never applies


def test_wallet_switch_off_removes_platform_certificates_only():
    from apps.card_designs.models import MakerspaceWalletCredentials
    from apps.card_designs.wallet import credentials
    space = make_space("pcb-wallet")
    assert credentials._fallback_allowed(space) is True
    MakerspaceWalletCredentials.objects.create(makerspace=space, use_platform_credentials=False)
    assert credentials._fallback_allowed(space) is False
    assert credentials.apple_for(space) is None and credentials.google_for(space) is None


def test_switch_is_scoped_to_the_space(switch_off):
    one, two = make_space("pcb-one"), make_space("pcb-two")
    ChannelConfiguration.objects.create(makerspace=one, channel="sms", provider="twilio", use_platform_sender=False)
    assert platform_allowed(one, "sms") is False and platform_allowed(two, "sms") is True


def test_queued_email_counts_and_failure_releases(switch_off):
    from apps.integrations.dispatch import dispatch_email
    space = make_space("pcb-queued")
    _limit(space, platform_email_monthly=1)
    first = dispatch_email(makerspace=space, to_email="a@example.test", subject="s", text_body="t",
                           event="x", stream="transactional")
    assert first.provider_source == "platform" and first.status != EmailLog.Status.SKIPPED
    assert pl.platform_used(space, "platform_email_monthly") == 1  # counted while still queued
    second = dispatch_email(makerspace=space, to_email="b@example.test", subject="s", text_body="t",
                            event="x", stream="transactional")
    assert second.status == EmailLog.Status.SKIPPED  # a burst cannot overshoot the limit
    EmailLog.objects.filter(pk=first.pk).update(status=EmailLog.Status.FAILED)
    assert pl.platform_used(space, "platform_email_monthly") == 0  # failure releases the reservation


def test_notice_goes_to_space_manager_and_superadmin_once_per_month(switch_off):
    from apps.accounts.models import User
    from apps.makerspaces.limits import reserve_notification_quota
    from apps.notifications.models_inbox import NotificationInboxRow
    from tests.makerspaces.l4_helpers import space_with_manager
    space, manager = space_with_manager("pcb-notice")
    other, other_manager = space_with_manager("pcb-notice-other")
    root = User.objects.create_user(username="pcb-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    _limit(space, platform_push_monthly=0)
    for _ in range(3):
        assert reserve_notification_quota(space, "native_push") is False
    rows = NotificationInboxRow.objects.filter(makerspace=space, event="platform_limit.reached")
    assert set(rows.values_list("user_id", flat=True)) == {manager.pk, root.pk}
    assert rows.get(user=manager).link == "/admin/usage"
    assert rows.get(user=root).link == "/admin/platform-spaces"  # a real console tab (notifications audit)
    assert AuditLog.objects.filter(action="platform_credential_limit.reached", makerspace=space).count() == 1
    assert not NotificationInboxRow.objects.filter(makerspace=other, event="platform_limit.reached").exists()
    assert other_manager.pk not in rows.values_list("user_id", flat=True)


def test_rail_refusal_spares_a_charge_raised_before_the_quota_was_reached(switch_off):
    from tests.open_items_0120.test_platform_credential_limits import _connect_charge
    space, _staff, payment = _connect_charge("pcb-rail")
    _limit(space, platform_payments_monthly_count=1)
    assert pl.rail_refusal(space, payment) is None  # the pending charge stays payable at the quota
