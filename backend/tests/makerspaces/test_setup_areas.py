"""Area application uses the real command, validation and audited services."""
import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.forms.models import model_to_dict

from apps.audit.models import AuditLog
from apps.makerspaces.capabilities import FEATURES, feature_required_modules, validate_capabilities
from apps.makerspaces.models import Makerspace, MembershipPlan
from apps.makerspaces.module_registry import core_module_keys
from apps.makerspaces.setup_areas import (
    AREAS, ALWAYS_MODULES, EXPLICIT_OPT_IN_FEATURES, modules_for, features_for, edition_for,
)


@pytest.fixture
def target(db):
    actor = get_user_model().objects.create_superuser(username="area-owner", email="owner@example.org", password="test")
    space = Makerspace.objects.create(name="Area space", slug="area-space", enabled_modules=list(core_module_keys()))
    return actor, space


def apply(monkeypatch, target, answers):
    actor, space = target
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(answers)))
    call_command("apply_setup_areas", makerspace=space.slug, actor=actor.username, answers_json="-", stdout=StringIO())
    space.refresh_from_db()
    return space


@pytest.mark.parametrize("area", list(AREAS))
def test_each_area_modules_and_all_satisfiable_features(area):
    modules = modules_for({area})
    assert modules == core_module_keys() | ALWAYS_MODULES | set(AREAS[area])
    features = set(features_for({area}))
    # L21b keeps search selected but dormant until the gallery is enabled.
    dormant_defaults = {"events.gallery_search"} if area == "events" else set()
    assert dormant_defaults <= features
    validate_capabilities(sorted(modules), sorted(features), dormant_defaults=dormant_defaults)
    for key, definition in FEATURES.items():
        if definition.parent_module in ALWAYS_MODULES | set(AREAS[area]):
            if key in EXPLICIT_OPT_IN_FEATURES or (key == "payments.loans" and area != "inventory"):
                assert key not in features
            elif set(feature_required_modules(key)) <= modules and set(definition.requires_features) <= features:
                assert key in features


@pytest.mark.parametrize("areas", [{"events"}, set(AREAS)])
def test_events_area_never_implicitly_enables_programme(areas):
    features = set(features_for(areas))
    assert EXPLICIT_OPT_IN_FEATURES.isdisjoint(features)
    assert all(not FEATURES[key].default_enabled for key in EXPLICIT_OPT_IN_FEATURES)


def test_events_setup_keeps_programme_off_in_persisted_capabilities(monkeypatch, target):
    space = apply(monkeypatch, target, {"areas": ["events"]})
    assert "events" in space.enabled_modules
    assert EXPLICIT_OPT_IN_FEATURES.isdisjoint(space.enabled_features)


@pytest.mark.parametrize("area", ["inventory", "machines", "events", "bookings", "membership"])
def test_online_features_need_payments_and_the_domain(area):
    key = f"payments.{ 'loans' if area == 'inventory' else area }"
    assert key not in features_for({area})
    assert key in features_for({area, "payments"})
    if area == "inventory":
        assert key not in features_for({"payments"})


def test_edition_derivation():
    assert edition_for({"events", "membership", "payments", "reports", "chat"}) == "events"
    assert edition_for({"bookings", "reports"}) == "bookings"
    assert edition_for({"events", "bookings"}) == "makerspace"
    assert edition_for({"inventory", "machines"}) == "makerspace"
    assert edition_for({"events"}, organization=True) == "organization"


def test_defaults_apply_audited_and_idempotently(monkeypatch, target):
    answers = {"areas": ["inventory", "machines"], "request_access": "accounts"}
    space = apply(monkeypatch, target, answers)
    assert set(space.enabled_modules) == modules_for({"inventory", "machines"})
    assert set(space.enabled_features) == set(features_for({"inventory", "machines"}))
    assert space.loan_policy.loan_renewal_mode == "auto"
    assert AuditLog.objects.filter(makerspace=space, action="makerspace.capabilities_changed").exists()
    assert AuditLog.objects.filter(makerspace=space, action="makerspace.return_policy_updated").exists()
    count = AuditLog.objects.filter(makerspace=space).count()
    apply(monkeypatch, target, answers)
    assert AuditLog.objects.filter(makerspace=space).count() == count


def test_inventory_off_keeps_core_and_existing_inventory(monkeypatch, target):
    from apps.inventory.models import InventoryProduct
    space = apply(monkeypatch, target, {"areas": ["inventory"]})
    product = InventoryProduct.objects.create(makerspace=space, name="Retained tool")
    space = apply(monkeypatch, target, {"areas": []})
    assert core_module_keys() <= set(space.enabled_modules)
    assert "loans.enabled" not in space.enabled_features
    assert "guest_handover" not in space.enabled_modules
    assert InventoryProduct.objects.filter(pk=product.pk).exists()
    assert AuditLog.objects.filter(makerspace=space, action__contains="purge").count() == 0


@pytest.mark.parametrize("bad_settings", [
    {"loan_policy": {"loan_max_active": -1}},
    {"loan_policy": {"misspelled": 7}},
    {"notifications": {"quiet_start": "25:00"}},
    {"features": {"security.staff_mfa_required": "yes"}},
    {"space": {"enabled_modules": []}},
])
def test_invalid_settings_roll_back_modules_and_audits(monkeypatch, target, bad_settings):
    _, space = target
    before = (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count())
    with pytest.raises(CommandError):
        apply(monkeypatch, target, {"areas": ["inventory"], "settings": bad_settings})
    space.refresh_from_db()
    assert (space.enabled_modules, space.enabled_features, AuditLog.objects.filter(makerspace=space).count()) == before


def test_membership_admission_plan_and_renewal_settings(monkeypatch, target):
    from apps.makerspaces.setup_defaults import APPLICATION_FORM
    answers = {"areas": ["membership"], "settings": {
        "admission": {"join_mode": "vouch", "vouches_required": 2, "vouch_replaces_approval": True, "application_schema": APPLICATION_FORM},
        "plan": {"name": "Standard", "interval": "monthly", "amount": "10.00", "currency": "inr", "auto_renew": True,
                 "renewal_open_days": 14, "renewal_grace_days": 3, "renewal_retries": 1, "reminder_days_before": [7, 1], "reminder_days_after": [1]},
    }}
    space = apply(monkeypatch, target, answers)
    assert space.admission_settings.vouches_required == 2
    assert space.admission_settings.vouch_replaces_approval
    plan = MembershipPlan.objects.get(makerspace=space)
    assert space.admission_settings.default_plan_id == plan.pk
    assert plan.auto_renew and plan.renewal_open_days == 14
    count = AuditLog.objects.filter(makerspace=space).count()
    apply(monkeypatch, target, answers)
    assert MembershipPlan.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space).count() == count


def test_change_preserves_old_switches_and_uninstalls_payment_rail(monkeypatch, target):
    space = apply(monkeypatch, target, {"areas": ["events", "payments"]})
    space.enabled_features.remove("events.offline_checkin")
    space.save(update_fields=["enabled_features"])
    space = apply(monkeypatch, target, {"areas": ["events", "reports"], "configure_areas": ["reports"]})
    assert "payments" not in space.enabled_modules
    assert "payments.events" not in space.enabled_features
    assert "events.offline_checkin" not in space.enabled_features
    assert "reports.saved_views" in space.enabled_features


def test_adding_payment_area_enables_existing_domain_payment_features(monkeypatch, target):
    apply(monkeypatch, target, {"areas": ["events", "bookings"]})
    space = apply(monkeypatch, target, {"areas": ["events", "bookings", "payments"], "configure_areas": ["payments"]})
    assert {"payments.events", "payments.bookings", "payments.enabled"} <= set(space.enabled_features)


def test_new_inventory_area_enables_loan_payments_when_rail_already_installed(monkeypatch, target):
    apply(monkeypatch, target, {"areas": ["payments"]})
    space = apply(monkeypatch, target, {"areas": ["inventory", "payments"], "configure_areas": ["inventory"]})
    assert "payments.loans" in space.enabled_features
    assert "loans.enabled" in space.enabled_features


def test_hiding_inventory_keeps_retained_loan_policy_and_charge_switches(monkeypatch, target):
    apply(monkeypatch, target, {"areas": ["inventory", "payments"], "settings": {"loan_policy": {"loan_max_active": 3}}})
    space = apply(monkeypatch, target, {"areas": ["payments"], "configure_areas": []})
    assert "loans.enabled" not in space.enabled_features
    assert {"charges.loans", "payments.loans", "loans.renewals"} <= set(space.enabled_features)
    assert space.loan_policy.loan_max_active == 3
    assert "containers" not in space.enabled_modules


def test_stdin_only_and_unknown_area(monkeypatch, target):
    with pytest.raises(CommandError):
        apply(monkeypatch, target, {"areas": ["unknown"]})
    with pytest.raises(CommandError):
        call_command("apply_setup_areas", makerspace=target[1].slug, answers_json='{"areas":[]}')


def test_event_default_changes_only_new_events_and_is_validated(monkeypatch, target):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.services import create_event
    space = apply(monkeypatch, target, {"areas": ["events"]})
    params = {"makerspace": space, "actor": target[0], "title": "Workshop", "description": "",
              "starts_at": timezone.now() + timedelta(days=2), "ends_at": timezone.now() + timedelta(days=2, hours=1),
              "location": "", "capacity": 0, "is_public": False}
    first = create_event(**params)
    assert first.registration_audience == "accounts"
    space = apply(monkeypatch, target, {"areas": ["events"], "settings": {"space": {"event_default_registration_audience": "invite"}}})
    second = create_event(**{**params, "makerspace": space})
    assert second.registration_audience == "invite"
    first.refresh_from_db()
    assert first.registration_audience == "accounts"
    explicit = create_event(**{**params, "makerspace": space}, registration_audience="members")
    assert explicit.registration_audience == "members"
    with pytest.raises(CommandError):
        apply(monkeypatch, target, {"areas": ["events"], "settings": {"space": {"event_default_registration_audience": "everyone"}}})


def test_digest_defaults_respect_saved_personal_opt_out(monkeypatch, target):
    from django.utils import timezone
    from apps.integrations.digests import digest_due
    from apps.notifications.models_inbox import MemberNotificationPreference
    space = apply(monkeypatch, target, {"areas": ["events"], "settings": {
        "notifications": {"quiet_start": "23:00", "quiet_end": "07:00", "digest_at": "09:00", "daily_digest_default": True},
    }})
    policy = space.notificationtimingpolicy
    assert policy.quiet_start.hour == 23 and policy.quiet_end.hour == 7
    assert policy.channels and policy.daily_digest_default
    assert digest_due(space, target[0].pk, "events", timezone.now()) is not None
    MemberNotificationPreference.objects.create(makerspace=space, user=target[0], feature="events", channel="email", enabled=True, daily_digest=False)
    assert digest_due(space, target[0].pk, "events", timezone.now()) is None
    space = apply(monkeypatch, target, {"areas": ["events"], "settings": {"notifications": {"channels": []}}})
    assert space.notificationtimingpolicy.channels == []


def test_all_areas_with_legacy_membership_exclusion(monkeypatch, target):
    space = apply(monkeypatch, target, {"areas": list(AREAS), "without": ["membership"]})
    assert "membership" not in space.enabled_modules
    assert "membership.auto_renew" not in space.enabled_features


def test_setup_fields_have_reviewed_tenant_dump_policies():
    from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES, validate_catalog
    from apps.tenant_migration.tenant_dump_types import AuthorityDisposition
    # The coordinator repins the digest; this also checks the production drift gate.
    validate_catalog()
    for label, field, sibling, disposition in (
        ("makerspaces.Makerspace", "event_default_registration_audience",
         ("events.Event", "registration_audience"), AuthorityDisposition.PRESERVE),
        ("integrations.NotificationTimingPolicy", "daily_digest_default",
         ("integrations.NotificationTimingPolicy", "digest_at"), AuthorityDisposition.DROP),
    ):
        rule = FIELD_POLICIES[(label, field)]
        assert rule.dispositions == FIELD_POLICIES[sibling].dispositions == (disposition,)
        assert rule.reason


@pytest.mark.parametrize("configuring", [[], ["events"]])
def test_change_preserves_standalone_and_notification_opt_outs(monkeypatch, target, configuring):
    space = apply(monkeypatch, target, {"areas": ["events"]})
    disabled = {"charges.enabled", "notifications.digests", "notifications.quiet_hours",
                "presence.geofence", "events.offline_checkin"}
    assert disabled <= set(space.enabled_features)
    space.enabled_features = sorted(set(space.enabled_features) - disabled)
    space.save(update_fields=["enabled_features"])
    before = set(space.enabled_features)
    space = apply(monkeypatch, target, {"areas": ["events"], "configure_areas": configuring})
    assert disabled.isdisjoint(space.enabled_features)
    assert set(space.enabled_features) == before


@pytest.mark.parametrize("stored_currency,supplied,expected", [
    ("inr", {}, "inr"), ("inr", {"currency": "eur"}, "eur"), (None, {}, "usd"),
])
@pytest.mark.parametrize("changing", [False, True])
def test_event_currency_defaults_only_without_a_stored_currency(
    monkeypatch, target, stored_currency, supplied, expected, changing,
):
    from apps.payments.models import MakerspacePaymentSettings
    if stored_currency:
        MakerspacePaymentSettings.objects.create(makerspace=target[1], default_currency=stored_currency)
    answers = {"areas": ["events"], "settings": supplied}
    if changing:
        answers["configure_areas"] = ["events"]
    space = apply(monkeypatch, target, answers)
    assert MakerspacePaymentSettings.objects.get(makerspace=space).default_currency == expected


@pytest.fixture
def configured_target(monkeypatch, target):
    space = apply(monkeypatch, target, {"areas": list(AREAS), "settings": {
        "loan_policy": {"loan_max_active": 3, "loan_max_items": 8, "default_loan_days": 21,
                        "loan_renewal_mode": "off", "loan_max_renewals": 4, "loan_renewal_days": 14},
        "space": {"event_default_registration_audience": "invite", "timezone": "Asia/Kolkata"},
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
