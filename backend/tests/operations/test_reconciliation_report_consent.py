"""Consent totals use account identity, current phone proof and canonical generation."""
import pytest

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.models_messaging_consent import MessagingConsent
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.reports_notification_consent import consented_members
from tests.operations.reconciliation_report_helpers import at, report_space
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def member(space, name):
    user = make_member(name, space, membership_role="member", role="requester")
    return verified_phone(user, "+14155552671")


def verified_phone(user, phone):
    # User.save clears verification whenever the number changes, so stamp it afterwards.
    user.phone_e164 = phone
    user.save(update_fields=["phone_e164", "phone_verified_at"])
    user.phone_verified_at = at("2026-10-01")
    user.save(update_fields=["phone_verified_at"])
    return user


def consent(space, user, config, **fields):
    return MessagingConsent.objects.create(makerspace=space, user=user, channel=config.channel,
        sender_key=config.sender_key, configuration_generation=config.generation,
        phone_e164=user.phone_e164, phone_verified_at=user.phone_verified_at,
        action=fields.pop("action", "opted_in"), source="member_settings", **fields)


def test_sms_counts_member_principal_and_invalidates_rotation_phone_instance_and_opt_out():
    space = report_space("recon-r-sms-consent")
    user = member(space, "recon-r-consent-member")
    config = ChannelConfiguration.objects.create(makerspace=space, channel="sms", provider="twilio",
        sender_key="sender-1", generation=1)
    consent(space, user, config)
    assert consented_members(space, "sms") == 1
    config.generation = 2
    config.save(update_fields=["generation"])
    assert consented_members(space, "sms") == 0
    consent(space, user, config)
    assert consented_members(space, "sms") == 1
    user.phone_verified_at = at("2026-10-02")
    user.save(update_fields=["phone_verified_at"])
    assert consented_members(space, "sms") == 0
    consent(space, user, config)
    consent(space, user, config, action="opted_out")
    assert consented_members(space, "sms") == 0


def test_staff_sharing_phone_is_never_a_consented_member_or_a_revoked_members_alias():
    space = report_space("recon-r-consent-kind")
    user = member(space, "recon-r-kind-member")
    staff = make_member("recon-r-kind-staff", space)
    verified_phone(staff, user.phone_e164)
    config = ChannelConfiguration.objects.create(makerspace=space, channel="sms", provider="twilio", sender_key="sender")
    consent(space, staff, config)
    assert consented_members(space, "sms") == 0
    consent(space, user, config)
    assert consented_members(space, "sms") == 1
    MakerspaceMembership.objects.filter(user=user, makerspace=space).update(status="revoked")
    assert consented_members(space, "sms") == 0


def test_whatsapp_uses_signed_endpoint_not_sms_phone_consent_and_honors_opt_out():
    space = report_space("recon-r-wa-consent")
    user = member(space, "recon-r-wa-member")
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider="meta",
        sender_key="wa-sender", integration_identity="installation", enabled=True, personal_enabled=True)
    consent(space, user, config)
    assert consented_members(space, "whatsapp") == 0  # An annotation cannot fabricate proof.
    NotificationEndpoint.objects.create(makerspace=space, user=user, channel="whatsapp", provider="meta",
        destination="+14155552671", provider_subject="proved", identity_digest="a" * 64,
        configuration=config, integration_identity=config.integration_identity, integration_generation=config.generation,
        verified_at=at("2026-10-01"), consented_at=at("2026-10-01"), consent_version="1")
    assert consented_members(space, "whatsapp") == 1
    consent(space, user, config, action="opted_out")
    assert consented_members(space, "whatsapp") == 0
