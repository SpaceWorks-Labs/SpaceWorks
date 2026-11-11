"""Per-space security settings: authority, re-auth, lock floor and audit (owner #110c, #111 Q9-Q13)."""

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.accounts.models import User
from apps.makerspaces import security_settings as service
from apps.makerspaces.models import Makerspace, MakerspaceSecurityLock
from apps.makerspaces.security_lock_guard import SecuritySettingLocked
from tests.accounts.account_factories import make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db
KEY = "security.passkeys_allowed"  # off is the stricter value (#157)
STRICT, LOOSE = False, True


def stored(space):
    from apps.makerspaces.security_settings_registry import stored_value
    return stored_value(Makerspace.objects.get(pk=space.pk), KEY)


@pytest.fixture
def ctx():
    space = Makerspace.objects.create(name="Sec", slug="sec-space")
    other = Makerspace.objects.create(name="Sec other", slug="sec-other")
    root = User.objects.create_superuser("sec-root", email="root@sec.test", password="x" * 20)
    manager = make_staff(space, username="sec-manager")
    inventory = make_staff(space, username="sec-inventory", role_slug="inventory_manager")
    foreign = make_staff(other, username="sec-foreign")
    return type("Ctx", (), dict(space=space, other=other, root=root, manager=manager,
                                inventory=inventory, foreign=foreign))


def client(user, recent=True):
    api = APIClient()
    if recent:
        force_recent_authenticate(api, user)
    else:
        api.force_authenticate(user=user, token={"surface": "staff_api" if user.account_kind == "staff" else "platform",
                                                 "kind": user.account_kind})
    return api


def url(space, lock_key=None):
    base = f"/api/v1/admin/makerspaces/{space.pk}/security-settings"
    return f"{base}/{lock_key}/lock" if lock_key else base


def row(response):
    return next(item for item in response.data["settings"] if item["key"] == KEY)


def test_space_manager_reads_and_changes_with_audit(ctx):
    api = client(ctx.manager)
    response = api.get(url(ctx.space))
    assert response.status_code == 200, response.data
    assert response.data["can_edit"] is True and response.data["can_lock"] is False
    assert response.data["edited_as"] == "space" and row(response)["value"] is LOOSE
    assert row(response)["strict_value"] is STRICT
    response = api.patch(url(ctx.space), {"values": {KEY: STRICT}}, format="json")
    assert response.status_code == 200, response.data
    assert row(response)["value"] is STRICT
    assert stored(ctx.space) is STRICT
    entry = AuditLog.objects.get(action="makerspace.security_setting_changed", makerspace=ctx.space)
    assert entry.actor == ctx.manager
    assert entry.meta == {"key": KEY, "from": LOOSE, "to": STRICT, "via": "space"}


def test_noop_change_records_nothing(ctx):
    client(ctx.manager).patch(url(ctx.space), {"values": {KEY: LOOSE}}, format="json")
    assert not AuditLog.objects.filter(action="makerspace.security_setting_changed").exists()


def test_superadmin_edits_as_platform(ctx):
    response = client(ctx.root).patch(url(ctx.space), {"values": {KEY: STRICT}}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["edited_as"] == "platform" and response.data["can_lock"] is True
    assert AuditLog.objects.get(action="makerspace.security_setting_changed").meta["via"] == "platform"


@pytest.mark.parametrize("who", ["inventory", "foreign"])
def test_module_managers_and_other_spaces_are_refused(ctx, who):
    api = client(getattr(ctx, who))
    assert api.get(url(ctx.space)).status_code == 403
    assert api.patch(url(ctx.space), {"values": {KEY: STRICT}}, format="json").status_code == 403
    assert stored(ctx.space) is LOOSE


def test_change_requires_recent_reauthentication(ctx):
    response = bearer_client(ctx.manager).patch(url(ctx.space), {"values": {KEY: STRICT}}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "recent_reauth_required"
    assert stored(ctx.space) is LOOSE


def test_lock_requires_superadmin_and_reauth(ctx):
    assert client(ctx.manager).put(url(ctx.space, KEY), {"floor": STRICT}, format="json").status_code == 403
    response = bearer_client(ctx.root).put(url(ctx.space, KEY), {"floor": STRICT}, format="json")
    assert response.status_code == 403
    assert not MakerspaceSecurityLock.objects.exists()


def test_lock_forces_on_and_space_manager_cannot_loosen(ctx):
    response = client(ctx.root).put(url(ctx.space, KEY), {"floor": STRICT, "note": "Insurer requires it"}, format="json")
    assert response.status_code == 200, response.data
    assert row(response)["value"] is STRICT and row(response)["lock"]["note"] == "Insurer requires it"
    actions = list(AuditLog.objects.filter(makerspace=ctx.space).values_list("action", flat=True))
    assert "makerspace.security_setting_locked" in actions and "makerspace.security_setting_changed" in actions
    manager_view = client(ctx.manager).get(url(ctx.space))
    assert row(manager_view)["lock"] == {"floor": STRICT, "note": "Insurer requires it",
                                          "locked_at": row(manager_view)["lock"]["locked_at"]}
    refused = client(ctx.manager).patch(url(ctx.space), {"values": {KEY: LOOSE}}, format="json")
    assert refused.status_code == 400
    assert refused.data["code"] == "security_setting_locked"
    assert stored(ctx.space) is STRICT


def test_superadmin_cannot_loosen_below_own_lock_until_unlocked(ctx):
    service.lock(ctx.root, ctx.space, KEY, STRICT)
    with pytest.raises(SecuritySettingLocked):
        service.set_setting(ctx.root, ctx.space, KEY, LOOSE)
    response = client(ctx.root).delete(url(ctx.space, KEY))
    assert response.status_code == 200, response.data
    assert row(response)["lock"] is None and row(response)["value"] is STRICT
    assert AuditLog.objects.filter(action="makerspace.security_setting_unlocked").count() == 1
    service.set_setting(ctx.manager, ctx.space, KEY, LOOSE)
    assert stored(ctx.space) is LOOSE


def test_boolean_lock_floor_must_be_true_and_unknown_keys_refused(ctx):
    api = client(ctx.root)
    assert api.put(url(ctx.space, KEY), {"floor": LOOSE}, format="json").status_code == 400
    assert api.put(url(ctx.space, "security.nope"), {"floor": True}, format="json").status_code == 400
    assert api.patch(url(ctx.space), {"values": {"security.nope": True}}, format="json").status_code == 400
    assert api.patch(url(ctx.space), {"values": {KEY: "yes"}}, format="json").status_code == 400
    assert api.delete(url(ctx.space, KEY)).status_code == 404


def test_audit_rows_are_visible_to_the_space_manager(ctx):
    service.lock(ctx.root, ctx.space, KEY, STRICT, "Policy")
    service.unlock(ctx.root, ctx.space, KEY)
    response = client(ctx.manager).get("/api/v1/admin/audit-logs", {"makerspace": ctx.space.pk})
    assert response.status_code == 200, response.data
    seen = {item["action"]: item["meta"] for item in response.data["results"]}
    assert seen["makerspace.security_setting_locked"] == {"key": KEY, "floor": STRICT, "note": "Policy"}
    assert seen["makerspace.security_setting_changed"]["via"] == "platform"
    assert "makerspace.security_setting_unlocked" in seen


def test_archived_space_is_refused(ctx):
    from django.utils import timezone
    Makerspace.objects.filter(pk=ctx.space.pk).update(archived_at=timezone.now())
    assert client(ctx.root).get(url(ctx.space)).status_code == 403


def test_staff_mfa_is_no_setting(ctx):
    response = client(ctx.manager).get(url(ctx.space))
    assert "security.staff_mfa_required" not in {item["key"] for item in response.data["settings"]}
    assert client(ctx.root).patch(url(ctx.space), {"values": {"security.staff_mfa_required": True}},
                                  format="json").status_code == 400
