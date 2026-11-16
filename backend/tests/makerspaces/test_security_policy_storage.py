"""Lane S0: ``policy`` storage for per-space security settings, its guard, and the frozen rows."""

import pytest
from django.core.exceptions import ValidationError

from apps.accounts import login_security_contract as contract
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces import security_settings as service
from apps.makerspaces import security_settings_registry as registry
from apps.makerspaces.models import Makerspace, MakerspaceSecurityPolicy
from apps.makerspaces.security_lock_guard import SecuritySettingLocked
from apps.makerspaces.security_settings_person import platform_default, space_value, strictest_for_staff
from tests.accounts.account_factories import grant_staff_role, make_staff

pytestmark = pytest.mark.django_db
ROWS = contract.PER_SPACE_SETTINGS


@pytest.fixture(autouse=True)
def frozen_rows_registered(monkeypatch):
    """The enforcing lanes register these rows; register them here to exercise storage."""
    rows = registry.REGISTRY + ROWS
    monkeypatch.setattr(registry, "REGISTRY", rows)
    monkeypatch.setattr(registry, "BY_KEY", {row.key: row for row in rows})
    monkeypatch.setattr(registry, "POLICY_KEYS", frozenset(row.key for row in ROWS))


@pytest.fixture
def ctx():
    space = Makerspace.objects.create(name="Pol", slug="pol-space")
    other = Makerspace.objects.create(name="Pol other", slug="pol-other")
    root = User.objects.create_superuser("pol-root", email="root@pol.test", password="x" * 20)
    manager = make_staff(space, username="pol-manager")
    return type("Ctx", (), dict(space=space, other=other, root=root, manager=manager))


def policy(space):
    return MakerspaceSecurityPolicy.objects.get(makerspace=space).values


def test_policy_writes_store_audit_and_show_in_effective(ctx):
    key = contract.STAFF_SESSION_MAX_HOURS.key
    assert registry.stored_value(ctx.space, key) == 168
    service.set_setting(ctx.manager, ctx.space, key, 24)
    assert policy(ctx.space) == {key: 24}
    entry = AuditLog.objects.get(action="makerspace.security_setting_changed")
    assert entry.meta == {"key": key, "from": 168, "to": 24, "via": "space"}
    row = next(item for item in service.effective(ctx.space) if item["key"] == key)
    assert row["value"] == 24 and row["kind"] == "int" and row["lock"] is None
    service.set_setting(ctx.manager, ctx.space, key, 24)
    assert AuditLog.objects.filter(action="makerspace.security_setting_changed").count() == 1


def test_invalid_values_are_refused(ctx):
    for key, value in ((contract.REMEMBERED_DEVICE_DAYS.key, 91), (contract.CAPTCHA_ON_SIGN_IN.key, "sometimes"),
                       (contract.STAFF_IP_ALLOWLIST.key, ["not-a-network"]), (contract.LOGIN_RISK_CHECK.key, 1)):
        with pytest.raises(ValidationError):
            service.set_setting(ctx.manager, ctx.space, key, value)
    assert not MakerspaceSecurityPolicy.objects.exists()


def test_cidrs_are_canonical(ctx):
    key = contract.STAFF_IP_ALLOWLIST.key
    service.set_setting(ctx.manager, ctx.space, key, [" 10.1.2.3/8", "2001:db8::1/32", "10.0.0.0/8"])
    assert policy(ctx.space)[key] == ["10.0.0.0/8", "2001:db8::/32"]


def test_lock_raises_the_stored_value_and_refuses_loosening(ctx):
    key = contract.CAPTCHA_ON_SIGN_IN.key
    service.lock(ctx.root, ctx.space, key, "after_failures")
    assert policy(ctx.space)[key] == "after_failures"
    with pytest.raises(SecuritySettingLocked):
        service.set_setting(ctx.manager, ctx.space, key, "off")
    service.set_setting(ctx.manager, ctx.space, key, "always")
    assert policy(ctx.space)[key] == "always"


def test_passkey_lock_forces_them_off(ctx):
    key = contract.PASSKEYS_ALLOWED.key
    with pytest.raises(ValidationError, match="forces it off"):
        service.lock(ctx.root, ctx.space, key, True)
    service.lock(ctx.root, ctx.space, key, False)
    assert policy(ctx.space)[key] is False
    with pytest.raises(SecuritySettingLocked):
        service.set_setting(ctx.manager, ctx.space, key, True)


def test_non_service_writes_keep_the_stored_values(ctx):
    key = contract.STAFF_IDLE_TIMEOUT_MINUTES.key
    service.set_setting(ctx.manager, ctx.space, key, 30)
    row = MakerspaceSecurityPolicy.objects.get(makerspace=ctx.space)
    row.values = {key: 0, "security.unregistered": True}
    row.save()
    assert policy(ctx.space) == {key: 30}
    MakerspaceSecurityPolicy.objects.create(makerspace=ctx.other, values={key: 5})
    assert policy(ctx.other) == {}


def test_service_write_below_a_floor_is_refused_by_the_guard(ctx):
    from apps.makerspaces import security_policy_store

    key = contract.REMEMBERED_DEVICE_DAYS.key
    service.lock(ctx.root, ctx.space, key, 30)
    with pytest.raises(SecuritySettingLocked):
        security_policy_store.write(ctx.space, key, 60)


def test_stricter_orders():
    idle = contract.STAFF_IDLE_TIMEOUT_MINUTES
    assert idle.stricter(0, 30) == 30 and idle.stricter(30, 0) == 30 and idle.stricter(10, 30) == 10
    allow = contract.STAFF_IP_ALLOWLIST
    assert allow.stricter([], ["10.0.0.0/8"]) == ["10.0.0.0/8"]
    assert allow.stricter(["10.1.0.0/16"], ["10.0.0.0/8"]) == ["10.1.0.0/16"]
    assert allow.stricter(["10.0.0.0/8"], ["10.1.0.0/16"]) == ["10.1.0.0/16"]
    assert allow.stricter(["192.0.2.0/24"], ["10.0.0.0/8"]) == ["10.0.0.0/8"]  # incomparable: the floor
    assert not allow.satisfies(["192.0.2.0/24"], ["10.0.0.0/8"])
    assert contract.PASSKEYS_ALLOWED.stricter(True, False) is False
    assert contract.LOGIN_RISK_CHECK.stricter(False, True) is True


def test_platform_default_comes_from_the_environment(settings):
    settings.LOGIN_REMEMBERED_DEVICE_DAYS = 30
    assert platform_default(contract.REMEMBERED_DEVICE_DAYS) == 30
    settings.LOGIN_REMEMBERED_DEVICE_DAYS = 500
    assert platform_default(contract.REMEMBERED_DEVICE_DAYS) == 90


def test_strictest_across_the_spaces_where_a_person_is_staff(ctx, settings):
    settings.LOGIN_REMEMBERED_DEVICE_DAYS = 60
    days, passkeys = contract.REMEMBERED_DEVICE_DAYS, contract.PASSKEYS_ALLOWED
    assert strictest_for_staff(ctx.manager, days) == 60
    service.set_setting(ctx.root, ctx.space, days.key, 45)
    service.set_setting(ctx.root, ctx.other, days.key, 14)
    service.set_setting(ctx.root, ctx.other, passkeys.key, False)
    assert strictest_for_staff(ctx.manager, days) == 45
    assert strictest_for_staff(ctx.manager, passkeys) is True
    grant_staff_role(ctx.manager, ctx.other, role_slug="inventory_manager")
    assert strictest_for_staff(ctx.manager, days) == 14
    assert strictest_for_staff(ctx.manager, passkeys) is False
    member = User.objects.create_user("pol-member", email="m@pol.test", password="x" * 20)
    assert strictest_for_staff(member, days) == 60


def test_space_value_applies_platform_default_and_lock(ctx):
    captcha = contract.CAPTCHA_ON_SIGN_IN
    assert space_value(ctx.space, captcha) == "off"
    service.lock(ctx.root, ctx.space, captcha.key, "always")
    assert space_value(ctx.space, captcha) == "always"
    with pytest.raises(ValueError):
        strictest_for_staff(ctx.manager, captcha)
