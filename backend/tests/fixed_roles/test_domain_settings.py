"""Each domain's feature switches and settings belong to that domain's manager."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines.models import Machine, MachineType
from apps.makerspaces.module_install import install_module
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db


def url(space, domain):
    return reverse("admin-makerspace-domain-settings", args=[space.pk, domain])


def actor(space, name, *slugs, machine_types=()):
    user = make_user(f"domain-{name}", access_status="active", account_kind="member" if slugs == ("member",) else "staff",
                     staff_makerspace=None if slugs == ("member",) else space)
    assign_builtin_roles(user, space, *slugs, machine_types=machine_types)
    # L17 (#101, C-11b): existing editors hold a per-person grant after the upgrade.
    from apps.makerspaces.models_settings_authority import ModuleSettingsGrant
    for slug, module in (("event_manager", "events"), ("booking_manager", "bookings"),
                         ("machine_manager", "machines"), ("inventory_manager", "inventory")):
        if slug in slugs:
            ModuleSettingsGrant.objects.create(makerspace=space, module=module, grantee=user)
    return user, authenticated_client(user)


def patch(client, space, domain, body):
    return client.patch(url(space, domain), body, format="json")


def features(space):
    space.refresh_from_db()
    return set(space.enabled_features)


def test_event_manager_reads_and_toggles_event_switches_and_is_audited():
    space = make_space("domain-events")
    install_module(space, "events")
    user, client = actor(space, "event-mgr", "event_manager")
    response = client.get(url(space, "events"))
    assert response.status_code == 200, response.data
    keys = {row["key"] for row in response.data["features"]}
    assert {"events.website", "events.embed", "events.api_read"} <= keys
    assert not keys & {"payments.events", "charges.events", "bookings.recurring"}
    assert response.data["editable"] is True
    assert "event_default_registration_audience" in response.data["settings"]

    response = patch(client, space, "events", {"features": {"events.website": True, "events.embed": True}})
    assert response.status_code == 200, response.data
    assert {"events.website", "events.embed"} <= features(space)
    response = patch(client, space, "events", {"features": {"events.website": False, "events.embed": False}})
    assert response.status_code == 200, response.data
    assert not {"events.website", "events.embed"} & features(space)
    assert AuditLog.objects.filter(
        action="makerspace.features_changed", makerspace=space, actor=user,
    ).count() == 2


def test_prerequisite_features_and_modules_are_enforced():
    space = make_space("domain-prereq")
    install_module(space, "events")
    _user, client = actor(space, "prereq-mgr", "event_manager")
    response = patch(client, space, "events", {"features": {"events.website": False, "events.embed": True}})
    assert response.status_code == 400
    assert "features" in response.data
    assert "events.embed" not in features(space)

    space.refresh_from_db()
    space.enabled_modules = [m for m in space.enabled_modules if m != "bookings"]
    space.save(update_fields=["enabled_modules"])
    _user, bookings = actor(space, "prereq-booker", "booking_manager")
    # The bookings module is not installed: its switches cannot be turned on here.
    response = patch(bookings, space, "bookings", {"features": {"bookings.website": True}})
    assert response.status_code == 400
    assert "bookings.website" not in features(space)


def test_event_default_audience_keeps_the_organization_audience_rule():
    space = make_space("domain-audience")
    install_module(space, "events")
    _user, client = actor(space, "audience-mgr", "event_manager")
    response = patch(client, space, "events", {
        "features": {"events.organization_audience": False},
        "settings": {"event_default_registration_audience": "participating_organizations"},
    })
    assert response.status_code == 400
    assert "event_default_registration_audience" in response.data["settings"]
    response = patch(client, space, "events", {
        "settings": {"event_default_registration_audience": "accounts", "event_reminder_lead_hours": [48]},
    })
    assert response.status_code == 200, response.data
    space.refresh_from_db()
    assert space.event_default_registration_audience == "accounts"
    assert space.event_reminder_lead_hours == [48]
    assert AuditLog.objects.filter(action="makerspace.updated", makerspace=space).exists()


def test_foreign_keys_modules_and_money_switches_are_refused():
    space = make_space("domain-foreign")
    install_module(space, "events")
    install_module(space, "bookings")
    _user, client = actor(space, "foreign-mgr", "event_manager")
    before = features(space)
    modules = list(space.enabled_modules)
    for body in (
        {"features": {"bookings.recurring": True}},
        {"features": {"payments.events": True}},
        {"features": {"charges.events": False}},
        {"settings": {"booking_requester_notifications_enabled": True}},
        {"settings": {"membership_policy": "open"}},
        {"enabled_modules": [*modules, "machines"]},
        {"enabled_features": []},
    ):
        response = patch(client, space, "events", body)
        assert response.status_code == 400, (body, response.data)
    assert features(space) == before
    space.refresh_from_db()
    assert space.enabled_modules == modules
    # Another domain's endpoint is outside this actor's scope entirely.
    assert client.get(url(space, "bookings")).status_code == 404
    assert patch(client, space, "bookings", {"features": {"bookings.recurring": True}}).status_code == 404
    assert client.get(url(space, "nonsense")).status_code == 404


def test_booking_manager_owns_booking_switches_and_settings_without_touching_others():
    space = make_space("domain-bookings")
    install_module(space, "bookings")
    install_module(space, "events")
    _boss, boss = actor(space, "bookings-boss", "space_manager")
    assert patch(boss, space, "events", {"features": {"events.invites": True}}).status_code == 200
    _user, client = actor(space, "booking-mgr", "booking_manager")
    response = patch(client, space, "bookings", {
        "features": {"bookings.recurring": True},
        "settings": {"booking_requester_notifications_enabled": True, "booking_reminder_lead_hours": [24]},
    })
    assert response.status_code == 200, response.data
    assert {"bookings.recurring", "events.invites"} <= features(space)
    space.refresh_from_db()
    assert space.booking_requester_notifications_enabled is True
    assert space.booking_reminder_lead_hours == [24]


def test_inventory_manager_owns_loan_switches_and_has_no_request_access_setting():
    space = make_space("domain-inventory")
    _user, client = actor(space, "inventory-mgr", "inventory_manager")
    response = client.get(url(space, "inventory"))
    assert response.status_code == 200, response.data
    assert {"loans.enabled", "loans.renewals", "inventory.self_checkout"} <= {
        row["key"] for row in response.data["features"]
    }
    assert response.data["settings"] == {}
    response = patch(client, space, "inventory", {"features": {"loans.renewals": True}})
    assert response.status_code == 200, response.data
    assert "loans.renewals" in features(space)
    # The account-less switch was removed (#75f): naming it is a foreign setting.
    response = patch(client, space, "inventory", {"settings": {"anonymous_requests_enabled": True}})
    assert response.status_code == 400


def test_machine_manager_may_write_only_while_their_types_cover_every_machine():
    space = make_space("domain-machines")
    install_module(space, "machines")
    laser, printer = [MachineType.objects.create(makerspace=space, name=name, slug=f"dm-{name.lower()}")
                      for name in ("Laser", "Printer")]
    Machine.objects.create(makerspace=space, machine_type=laser, name="Laser one")
    _user, client = actor(space, "machine-mgr", "machine_manager", machine_types=[laser])
    response = patch(client, space, "machines", {"features": {"machines.public_detail": True}})
    assert response.status_code == 200, response.data
    assert "machines.public_detail" in features(space)

    Machine.objects.create(makerspace=space, machine_type=printer, name="Printer one")
    response = client.get(url(space, "machines"))
    assert response.status_code == 200 and response.data["editable"] is False
    response = patch(client, space, "machines", {"features": {"machines.public_detail": False}})
    assert response.status_code == 403
    assert "machines.public_detail" in features(space)

    _boss, boss = actor(space, "machine-boss", "space_manager")
    response = patch(boss, space, "machines", {"features": {"machines.public_detail": False}})
    assert response.status_code == 200, response.data


def test_member_and_handover_are_refused_on_every_domain():
    space = make_space("domain-refused")
    install_module(space, "events")
    install_module(space, "bookings")
    install_module(space, "machines")
    for name, slug in (("member", "member"), ("handover", "handover")):
        _user, client = actor(space, name, slug)
        for domain in ("events", "bookings", "machines", "inventory"):
            assert client.get(url(space, domain)).status_code == 404, (slug, domain)
            assert patch(client, space, domain, {"features": {}}).status_code == 404, (slug, domain)


def test_space_manager_reaches_every_domain_and_other_spaces_stay_hidden():
    space = make_space("domain-boss")
    other = make_space("domain-boss-other")
    for key in ("events", "bookings", "machines"):
        install_module(space, key)
    _user, client = actor(space, "boss", "space_manager")
    for domain, key in (("events", "events.invites"), ("bookings", "bookings.recurring"),
                        ("machines", "machines.material_catalogue"), ("inventory", "loans.limits")):
        response = patch(client, space, domain, {"features": {key: True}})
        assert response.status_code == 200, (domain, response.data)
        assert key in features(space)
        assert client.get(url(other, domain)).status_code == 404
