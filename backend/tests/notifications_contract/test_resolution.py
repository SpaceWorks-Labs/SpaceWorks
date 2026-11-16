import pytest

from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_resolution import resolve
from apps.notifications.models_inbox import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def choose(c, channels, fallback=True):
    return NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=channels, email_fallback=fallback)


def channels(envelope):
    return {target.channel for target in resolve(envelope)}


def test_multiple_channels_are_all_selected(contract):
    choose(contract, ["telegram", "email"])
    assert channels(contract.envelope()) == {"telegram", "email"}


def test_verified_chat_prevents_optional_email_fallback(contract):
    choose(contract, ["telegram"])
    assert channels(contract.envelope()) == {"telegram"}


@pytest.mark.parametrize("change", ["revoked", "generation", "consent", "source", "standing", "configuration"])
def test_live_eligibility_reloads_every_predicate(contract, change):
    c = contract
    choose(c, ["telegram"], fallback=False)
    envelope = c.envelope()
    assert channels(envelope) == {"telegram"}
    if change == "revoked":
        c.endpoint.verification_state = "revoked"
        c.endpoint.save(update_fields=["verification_state"])
    elif change == "generation":
        c.config.generation += 1
        c.config.save()
    elif change == "consent":
        # Production disconnect stamps revoked_at; it never manufactures consent.
        from django.utils import timezone
        c.endpoint.revoked_at = timezone.now()
        c.endpoint.save(update_fields=["revoked_at"])
    elif change == "source":
        c.state["valid"] = False
    elif change == "standing":
        c.user.is_active = False
        c.user.save(update_fields=["is_active"])
    else:
        c.config.personal_enabled = False
        c.config.save()
    assert channels(envelope) == set()


def test_fallback_requires_both_tenant_and_user_permission(contract):
    c = contract
    pref = choose(c, ["slack"])
    envelope = c.envelope()
    assert channels(envelope) == {"email"}
    pref.email_fallback = False
    pref.save()
    assert channels(envelope) == set()
    pref.email_fallback = True
    pref.save()
    ChannelConfiguration.objects.create(makerspace=c.space, channel="email", provider="builtin",
        enabled=True, personal_enabled=True, email_fallback=False)
    assert channels(envelope) == set()


def test_fallback_never_bypasses_existing_unsubscribe(contract):
    c = contract
    choose(c, ["slack"])
    MemberNotificationPreference.objects.create(makerspace=c.space, user=c.user,
        feature="hardware_requests", channel="email", enabled=False)
    assert channels(c.envelope()) == set()


def test_return_reminder_email_is_independent_of_chat_and_module(contract):
    c = contract
    choose(c, ["telegram"], fallback=False)
    MemberNotificationPreference.objects.create(makerspace=c.space, user=c.user,
        feature="hardware_requests", channel="email", enabled=False)
    c.space.enabled_modules = [m for m in c.space.enabled_modules if m != "email"]
    c.space.save(update_fields=["enabled_modules"])
    assert channels(c.envelope(event="return_reminder")) == {"telegram", "email"}
    assert channels(c.envelope(event="closed_with_issue")) == {"telegram"}


def test_suppression_still_blocks_mandatory_mail(contract):
    from apps.integrations.email_preferences import address_hash
    from apps.integrations.models_suppression import EmailSuppression
    c = contract
    choose(c, [], fallback=False)
    EmailSuppression.objects.create(makerspace=c.space, address_hash=address_hash(c.space.pk, c.user.email), reason="bounce")
    assert channels(c.envelope(event="return_reminder")) == set()


def test_account_only_owner_has_no_universal_membership_requirement(contract):
    c = contract
    c.user.makerspace_memberships.all().delete()
    choose(c, ["telegram"])
    assert channels(c.envelope()) == {"telegram"}


def test_staff_source_must_also_pass_live_staff_scope(contract, monkeypatch):
    c = contract
    choose(c, ["telegram"])
    monkeypatch.setattr("apps.integrations.staff_notifications.staff_user_ids_for_feature", lambda *args: [])
    assert channels(c.envelope(audience="staff")) == set()


def test_manager_default_telegram_member_default_email(contract, monkeypatch):
    c = contract
    assert "email" in channels(c.envelope())
    monkeypatch.setattr("apps.accounts.rbac.effective_actions", lambda *args: {"manage_events"})
    assert channels(c.envelope()) == {"telegram"}


def test_module_reinstall_never_reactivates_personal_consent(contract):
    c = contract
    choose(c, ["telegram"], fallback=False)
    original = list(c.space.enabled_modules)
    c.space.enabled_modules = [key for key in original if key != "telegram"]
    c.space.save(update_fields=["enabled_modules"])
    c.space.enabled_modules = original
    c.space.save(update_fields=["enabled_modules"])
    c.endpoint.refresh_from_db()
    c.config.refresh_from_db()
    assert c.endpoint.revoked_at is not None and c.config.generation > c.endpoint.integration_generation
    assert channels(c.envelope()) == set()
