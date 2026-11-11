"""L17 settings authority (#101, #128 C-11): grants, locks, the C-11d exception, exclusions."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models_settings_authority import ModuleSettingLock, ModuleSettingsGrant
from apps.makerspaces.module_install import install_module
from apps.makerspaces.settings_authority import (
    FIXED_EXCEPTION, MODULE_GRANT, SPACE_MANAGER, SettingWriteRefused, assert_setting_write, decide,
)
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def domain_url(space, domain):
    return reverse("admin-makerspace-domain-settings", args=[space.pk, domain])


def grants_url(space):
    return reverse("admin-settings-authority-grants", args=[space.pk])


def locks_url(space):
    return reverse("admin-settings-authority-locks", args=[space.pk])


def effective_url(space):
    return reverse("admin-settings-authority-effective", args=[space.pk])


def policy_url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/return-policy"


@pytest.fixture
def space():
    space = make_space("authority")
    install_module(space, "events")
    return space


def people(space, *pairs):
    return [staff_account(space, f"auth-{name}", slug) for name, slug in pairs]


def test_event_manager_is_read_only_until_granted_then_edits_with_audit(space):
    manager, events = people(space, ("sm", "space_manager"), ("em", "event_manager"))
    em = authenticated_client(events)
    response = em.get(domain_url(space, "events"))
    assert response.status_code == 200 and response.data["editable"] is False
    assert all(row["editable"] is False for row in response.data["features"])
    refused = em.patch(domain_url(space, "events"), {"features": {"events.website": True}}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"
    space.refresh_from_db()
    assert "events.website" not in space.enabled_features

    sm = authenticated_client(manager)
    assert sm.put(grants_url(space), {"module": "events", "grantee_ids": [events.pk]}, format="json").status_code == 200
    grant = ModuleSettingsGrant.objects.get(makerspace=space, grantee=events, revoked_at__isnull=True)
    assert AuditLog.objects.filter(action="settings.grant_created", makerspace=space, actor=manager).exists()
    response = em.patch(domain_url(space, "events"), {"features": {"events.website": True}}, format="json")
    assert response.status_code == 200, response.data
    row = AuditLog.objects.get(action="settings.changed", makerspace=space, actor=events)
    assert row.meta["via"] == MODULE_GRANT and row.meta["grant_id"] == grant.pk
    assert row.meta["key"] == "events.website" and row.meta["from"] is False and row.meta["to"] is True

    # Revoking returns the manager to read-only; the history row stays.
    assert sm.put(grants_url(space), {"module": "events", "grantee_ids": []}, format="json").status_code == 200
    grant.refresh_from_db()
    assert grant.revoked_at is not None and grant.revoked_by == manager
    assert em.patch(domain_url(space, "events"), {"features": {"events.website": False}},
                    format="json").status_code == 403
    with pytest.raises(ValueError):
        grant.delete()


def test_space_manager_always_edits_and_a_lock_blocks_only_delegated_edits(space):
    manager, events = people(space, ("lock-sm", "space_manager"), ("lock-em", "event_manager"))
    ModuleSettingsGrant.objects.create(makerspace=space, module="events", grantee=events)
    sm, em = authenticated_client(manager), authenticated_client(events)
    response = sm.put(locks_url(space), {"setting_key": "event_reminder_lead_hours", "locked": True,
                                         "note": "Fixed by policy"}, format="json")
    assert response.status_code == 200 and response.data[0]["setting_key"] == "event_reminder_lead_hours"
    refused = em.patch(domain_url(space, "events"), {"settings": {"event_reminder_lead_hours": [12]}}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_locked"
    detail = em.get(domain_url(space, "events")).data
    assert detail["setting_permissions"]["event_reminder_lead_hours"] == {"editable": False, "locked": True}
    ok = sm.patch(domain_url(space, "events"), {"settings": {"event_reminder_lead_hours": [12]}}, format="json")
    assert ok.status_code == 200, ok.data
    assert AuditLog.objects.get(action="settings.changed", actor=manager).meta["via"] == SPACE_MANAGER
    assert sm.put(locks_url(space), {"setting_key": "event_reminder_lead_hours", "locked": False},
                  format="json").data == []
    assert ModuleSettingLock.objects.get(makerspace=space).released_by == manager
    assert {"settings.lock_created", "settings.lock_released"} <= set(
        AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))


def test_inventory_manager_changes_rental_timing_without_a_grant_but_not_past_a_lock(space):
    manager, inventory = people(space, ("im-sm", "space_manager"), ("im", "inventory_manager"))
    im = authenticated_client(inventory)
    response = im.patch(policy_url(space), {"default_loan_days": 9, "loan_renewal_days": 3}, format="json")
    assert response.status_code == 200, response.data
    rows = AuditLog.objects.filter(action="settings.changed", actor=inventory)
    assert {row.meta["key"] for row in rows} == {"default_loan_days", "loan_renewal_days"}
    assert {row.meta["via"] for row in rows} == {FIXED_EXCEPTION}
    # The other lending limits need the inventory grant.
    refused = im.patch(policy_url(space), {"loan_max_active": 2}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"
    authenticated_client(manager).put(locks_url(space), {"setting_key": "default_loan_days", "locked": True},
                                      format="json")
    locked = im.patch(policy_url(space), {"default_loan_days": 4}, format="json")
    assert locked.status_code == 403 and locked.data["code"] == "setting_locked"
    assert decide(inventory, space, "inventory", "loans.renewals").via == FIXED_EXCEPTION


def test_machine_manager_grant_is_limited_to_their_machine_types(space):
    install_module(space, "machines")
    laser, printer = [MachineType.objects.create(makerspace=space, name=n, slug=f"sa-{n.lower()}")
                      for n in ("Laser", "Printer")]
    Machine.objects.create(makerspace=space, machine_type=laser, name="Laser one")
    machines = staff_account(space, "auth-mm", "machine_manager", machine_types=[laser])
    ModuleSettingsGrant.objects.create(makerspace=space, module="machines", grantee=machines)
    mm = authenticated_client(machines)
    assert mm.patch(domain_url(space, "machines"), {"features": {"machines.public_detail": True}},
                    format="json").status_code == 200
    Machine.objects.create(makerspace=space, machine_type=printer, name="Printer one")
    refused = mm.patch(domain_url(space, "machines"), {"features": {"machines.public_detail": False}}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"


def test_security_and_finance_settings_are_never_delegated(space):
    inventory, = people(space, ("fin-im", "inventory_manager"))
    ModuleSettingsGrant.objects.create(makerspace=space, module="inventory", grantee=inventory)
    for module, key in (("inventory", "security.passkeys_allowed"), ("inventory", "charges.loans"),
                        ("payments", "payments.loans"), ("finance", "tax_rate")):
        with pytest.raises(SettingWriteRefused) as caught:
            assert_setting_write(inventory, space, module, key)
        assert caught.value.code == "setting_not_delegated"
    manager, = people(space, ("fin-sm", "space_manager"))
    assert assert_setting_write(manager, space, "payments", "payments.loans").via == SPACE_MANAGER


def test_grant_and_lock_endpoints_are_space_manager_only_and_validate(space):
    manager, events, booking = people(space, ("ep-sm", "space_manager"), ("ep-em", "event_manager"),
                                      ("ep-bm", "booking_manager"))
    em = authenticated_client(events)
    assert em.get(grants_url(space)).status_code == 403
    assert em.put(grants_url(space), {"module": "events", "grantee_ids": [events.pk]}, format="json").status_code == 403
    assert em.put(locks_url(space), {"setting_key": "events.website", "locked": True}, format="json").status_code == 403
    sm = authenticated_client(manager)
    # A booking manager is not an events manager; a space manager needs no grant.
    for ids in ([booking.pk], [manager.pk]):
        assert sm.put(grants_url(space), {"module": "events", "grantee_ids": ids}, format="json").status_code == 400
    assert sm.put(locks_url(space), {"setting_key": "security.passkeys_allowed", "locked": True},
                  format="json").status_code == 400
    assert sm.put(grants_url(space), {"module": "shop", "grantee_ids": []}, format="json").status_code == 400
    other = make_space("authority-other")
    assert sm.get(grants_url(other)).status_code == 404


def test_effective_lists_only_the_callers_modules(space):
    events, = people(space, ("eff-em", "event_manager"))
    response = authenticated_client(events).get(effective_url(space))
    assert response.status_code == 200
    assert [row["module"] for row in response.data["modules"]] == ["events"]
    keys = {row["key"]: row for row in response.data["modules"][0]["keys"]}
    assert keys["events.website"]["editable"] is False and keys["events.website"]["code"] == "setting_not_delegated"
    manager, = people(space, ("eff-sm", "space_manager"))
    full = authenticated_client(manager).get(effective_url(space)).data["modules"]
    assert {row["module"] for row in full} == {"events", "bookings", "machines", "inventory"}
    assert all(key["editable"] for row in full for key in row["keys"])
    member = User.objects.create_user("eff-member")
    assert authenticated_client(member).get(effective_url(space)).status_code in {403, 404}
