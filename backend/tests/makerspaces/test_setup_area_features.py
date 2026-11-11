"""The all-features shortcut preserves saved settings and standalone switches."""
from django.core.management import CommandError
from django.forms.models import model_to_dict
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.setup_areas import AREAS, modules_for, features_for
from tests.makerspaces.test_setup_areas import apply, target  # noqa: F401


@pytest.fixture
def configured_target(monkeypatch, target):
    # Timezone belongs to the profile editor, not the setup-area answers API.
    space = target[1]
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    space = apply(monkeypatch, target, {"areas": list(AREAS), "settings": {
        "loan_policy": {"loan_max_active": 3, "loan_max_items": 8, "default_loan_days": 21,
                        "loan_renewal_mode": "off", "loan_max_renewals": 4, "loan_renewal_days": 14},
        "space": {"event_default_registration_audience": "invite"},
        "admission": {"join_mode": "vouch", "vouches_required": 2, "voucher_min_tenure_days": 60,
                      "voucher_pending_limit": 5, "vouch_expiry_days": 45, "vouch_replaces_approval": True,
                      "application_schema": [{"id": "project", "label": "What will you make?",
                                              "type": "paragraph", "required": True, "options": []}]},
        "notifications": {"quiet_start": "23:30", "quiet_end": "06:30", "digest_at": "10:15",
                          "daily_digest_default": True, "channels": ["email"]},
        "currency": "inr",
    }})
    # Keep the area active, but opt out of every other area-supported feature.
    space.enabled_features = ["loans.enabled"]
    space.save(update_fields=["enabled_features"])
    return target[0], space


def configured_settings(space):
    from apps.payments.models import MakerspacePaymentSettings
    return {
        "loan_policy": model_to_dict(space.loan_policy),
        "event_audience": space.event_default_registration_audience,
        "timezone": space.timezone,
        "admission": model_to_dict(space.admission_settings),
        "notifications": model_to_dict(space.notificationtimingpolicy),
        "payment": model_to_dict(MakerspacePaymentSettings.objects.get(makerspace=space)),
    }


def test_enable_all_features_preserves_settings_and_is_idempotent(monkeypatch, configured_target):
    _, space = configured_target
    before_settings = configured_settings(space)
    before_features = set(space.enabled_features)
    expected = set(features_for(AREAS))
    assert expected - before_features  # The run must restore stored feature opt-outs.
    answers = {"areas": list(AREAS), "configure_areas": [], "enable_area_features": True}
    space = apply(monkeypatch, configured_target, answers)
    assert configured_settings(space) == before_settings
    assert set(space.enabled_features) == expected
    assert set(space.enabled_modules) == modules_for(AREAS)
    assert AuditLog.objects.filter(makerspace=space, action="makerspace.features_changed").exists()
    before_repeat = (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count())
    space = apply(monkeypatch, configured_target, answers)
    assert configured_settings(space) == before_settings
    assert (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count()) == before_repeat


def test_retired_staff_mfa_switch_is_no_setup_answer(monkeypatch, target):
    # Release 2 (S-A): staff MFA is a platform rule; the old per-space switch is refused.
    with pytest.raises(CommandError):
        apply(monkeypatch, target, {"areas": ["events"], "settings": {
            "features": {"security.staff_mfa_required": True}}})


def test_enable_all_features_keeps_module_exclusions(monkeypatch, configured_target):
    space = apply(monkeypatch, configured_target, {"areas": list(AREAS), "configure_areas": [],
                                                 "enable_area_features": True, "without": ["telegram"]})
    wanted = modules_for(AREAS) - {"telegram"}
    assert set(space.enabled_modules) == wanted
    assert set(space.enabled_features) == set(features_for(AREAS, wanted))


@pytest.mark.parametrize("invalid", ["yes", 1, 0, None, [], {}])
def test_enable_all_features_requires_a_boolean_and_rolls_back(monkeypatch, target, invalid):
    _, space = target
    before = (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count())
    with pytest.raises(CommandError, match="enable_area_features"):
        apply(monkeypatch, target, {"areas": list(AREAS), "configure_areas": [], "enable_area_features": invalid})
    space.refresh_from_db()
    assert (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count()) == before
