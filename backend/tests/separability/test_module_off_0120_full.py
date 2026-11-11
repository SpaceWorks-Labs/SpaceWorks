"""Full per-module on/off audit for release 0.12.0 (decisions 218, 223, 225).

For every capability added in 221-224: the registry chain is right, its routes answer the
typed 404 while it is off, its sweeps do nothing, its cross-module hooks are inert, its
child is inert under an off parent, and the optional-area analytics views follow the switch.
Ordinary settings profile; the deployment tombstone profile lives in `tests/tombstone`.
"""

from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.platform import feature_enabled
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db

# key -> (parent module, required features, required modules)
NEW_CAPABILITIES = {
    "membership.guest_passes": ("membership", (), ()),
    "membership.day_passes": ("membership", ("membership.guest_passes",), ()),
    "events.guest_passes": ("events", ("membership.guest_passes",), ()),
    "membership.minors": ("membership", (), ()),
    "membership.volunteer_credit": ("membership", (), ()),
    "membership.join_funnel": ("membership", (), ()),
    "membership.wallet_passes": ("membership", (), ()),
    "bookings.organization_bookings": ("bookings", (), ()),
    "machines.induction_events": ("machines", (), ("events",)),
    "machines.supervised_sessions": ("machines", (), ()),
    "safety.incidents": (None, (), ()),
}
ALL_MODULES = ("membership", "events", "bookings", "machines", "machine_service", "member_accounts", "analytics")


def _space(slug, *, modules=ALL_MODULES, features=()):
    space = make_space(slug)
    space.enabled_modules = sorted(set(modules))  # exactly the named modules: make_space already enables many
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def _all_on(slug):
    return _space(slug, features=tuple(NEW_CAPABILITIES))


@pytest.mark.parametrize("key", sorted(NEW_CAPABILITIES))
def test_registry_chain(key):
    parent, needs_features, needs_modules = NEW_CAPABILITIES[key]
    definition = FEATURES[key]
    assert definition.parent_module == parent
    assert set(needs_features) <= set(definition.requires_features)
    assert set(needs_modules) <= set(definition.requires_modules)
    assert definition.default_enabled is False


@pytest.mark.parametrize("key", sorted(NEW_CAPABILITIES))
def test_capability_is_off_when_unset_and_inert_under_an_off_parent(key):
    space = _all_on(f"full-{key.replace('.', '-').replace('_', '-')}")
    assert feature_enabled(space, key)
    parent, needs_features, needs_modules = NEW_CAPABILITIES[key]
    for module in filter(None, (parent, *needs_modules)):
        space.enabled_modules = [m for m in ALL_MODULES if m != module]
        assert not feature_enabled(space, key), (key, module)
        space.enabled_modules = list(ALL_MODULES)
    for feature in needs_features:
        space.enabled_features = [f for f in NEW_CAPABILITIES if f != feature]
        assert not feature_enabled(space, key), (key, feature)
    space.enabled_features = [f for f in NEW_CAPABILITIES if f != key]
    assert not feature_enabled(space, key)


# (url name, kwargs builder, capability switched off)
STAFF_ROUTES = (
    ("admin-guest-passes", "guest_passes"), ("admin-day-pass-products", "day_passes"),
    ("admin-minors", "minors"), ("admin-guardian-terms", "minors"),
    ("admin-volunteer-hours", "volunteer_credit"), ("admin-volunteer-credits", "volunteer_credit"),
)


@pytest.mark.parametrize("name,short", STAFF_ROUTES)
def test_staff_route_answers_the_typed_404_while_its_capability_is_off(name, short):
    key = f"membership.{short}"
    space = _space(f"route-{name}", features=[k for k in NEW_CAPABILITIES if k != key and key not in
                                              FEATURES[k].requires_features])
    admin = make_user(f"su-{name}", role=User.Role.SUPERADMIN)
    response = authenticated_client(admin).get(reverse(name, kwargs={"makerspace_id": space.pk}))
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "feature_disabled"
    assert response.json()["feature"] == key


def test_incident_register_answers_404_and_record_incident_writes_nothing_while_off():
    from apps.maintenance.incidents.models import Incident
    from apps.maintenance.incidents.services import record_incident

    space = _space("incidents-off")
    admin = make_user("su-incidents", role=User.Role.SUPERADMIN)
    response = authenticated_client(admin).get(reverse("admin-incidents", kwargs={"makerspace_id": space.pk}))
    assert response.status_code == 404 and response.json()["feature"] == "safety.incidents"
    assert record_incident(space, title="Guest kept the drill") is None
    assert not Incident.objects.filter(makerspace=space).exists()


def test_public_day_passes_answer_404_while_day_passes_are_off():
    space = _space("public-day-off", features=("membership.guest_passes",))
    response = authenticated_client(make_user("anon-day")).get(
        reverse("public-day-passes", kwargs={"makerspace_slug": space.slug}))
    assert response.status_code == 404


def test_guest_pass_hooks_are_inert_while_off():
    """Walk-ins, the on-site waiver and borrowing behave exactly as before guest passes existed."""
    from apps.makerspaces.guest_pass_queries import active_pass_for, require_waiver
    from apps.makerspaces.guest_pass_policy import day_passes_on, guest_passes_on
    from apps.makerspaces.models import MakerspaceWaiver
    from apps.makerspaces.walk_in_services import walk_in_creates_guest_pass

    space = _space("guest-hooks-off", features=("membership.day_passes",))
    MakerspaceWaiver.objects.create(makerspace=space, version="1", body="Be safe.", is_active=True)
    person = make_user("guest-hooks-person", access_status=User.AccessStatus.ACTIVE)
    assert not guest_passes_on(space) and not day_passes_on(space)
    assert walk_in_creates_guest_pass(space) is False
    assert active_pass_for(person, space) is None
    assert require_waiver(person, space) is None  # no WaiverAcceptanceRequired while passes are off


def test_minor_checks_are_skipped_while_minors_are_off():
    from apps.makerspaces.minors_guard import evaluate, require_minor_clearance

    space = _space("minors-off")
    person = make_user("minors-off-person", access_status=User.AccessStatus.ACTIVE)
    for purpose in ("membership", "event", "guest_pass", "presence", "borrow", "machine"):
        assert evaluate(person, space, purpose) is None
        require_minor_clearance(person, space, purpose)


def test_volunteer_credit_never_reduces_a_charge_while_off():
    from decimal import Decimal

    from apps.makerspaces.volunteer_credit import reduce_charge

    space = _space("volunteer-off")
    person = make_user("volunteer-off-person")
    assert reduce_charge(space, person, Decimal("50.00"), "INR", term_days=30) == (Decimal("50.00"), [])


def test_join_followup_sweep_is_a_no_op_with_events_off(monkeypatch):
    from apps.events import join_followup
    from apps.makerspaces.models import CommunityPolicy

    sent = []
    monkeypatch.setattr(join_followup, "_send_for_space", lambda space, now: sent.append(space.pk) or 1)
    off = _space("funnel-events-off", modules=("membership",), features=("membership.join_funnel",))
    CommunityPolicy.objects.create(makerspace=off, join_followup_enabled=True)
    unset = _space("funnel-off")
    CommunityPolicy.objects.create(makerspace=unset, join_followup_enabled=True)
    on = _space("funnel-on", features=("membership.join_funnel",))
    CommunityPolicy.objects.create(makerspace=on, join_followup_enabled=True)
    assert join_followup.send_join_followups() == 1
    assert sent == [on.pk]
    assert not join_followup._funnel_live(off) and not join_followup._funnel_live(unset)


def test_guest_pass_sweep_skips_spaces_with_passes_off(monkeypatch):
    from apps.makerspaces import guest_pass_lifecycle, guest_pass_sweeps

    seen = []
    monkeypatch.setattr(guest_pass_lifecycle, "expire_due_passes", lambda space, now: seen.append(space.pk) or 0)
    monkeypatch.setattr("apps.makerspaces.notifications_guest_passes.send_expiring_notices",
                        lambda now, makerspace=None: 0)
    monkeypatch.setattr("apps.hardware_requests.guest_liability.record_outstanding_at_pass_end",
                        lambda now, makerspace=None: 0)
    off = _space("sweep-off")
    on = _space("sweep-on", features=("membership.guest_passes",))
    guest_pass_sweeps.run_guest_pass_sweeps()
    assert on.pk in seen and off.pk not in seen


def test_guest_certification_stops_unlocking_machines_while_induction_is_off():
    from apps.machines.induction import holds_certification
    from apps.machines.models import GuestCertificationGrant
    from tests.machines.certification_helpers import _certification, _machine_type

    space = _space("induction-off", features=("machines.induction_events",))
    machine_type = _machine_type(space)
    certification = _certification(space, machine_type)
    guest = make_user("induction-guest", access_status=User.AccessStatus.ACTIVE)
    GuestCertificationGrant.objects.create(makerspace=space, certification_type=certification, user=guest)
    assert holds_certification(guest, machine_type, space)
    space.enabled_features = []
    space.save(update_fields=["enabled_features"])
    assert not holds_certification(guest, machine_type, space)
    space.enabled_features = ["machines.induction_events"]
    space.enabled_modules = [m for m in ALL_MODULES if m != "events"]
    space.save(update_fields=["enabled_features", "enabled_modules"])
    assert not holds_certification(guest, machine_type, space)  # child inert under an off Events module
    assert GuestCertificationGrant.objects.filter(makerspace=space).count() == 1  # data kept


def test_supervised_session_refuses_an_event_binding_with_events_off():
    from apps.machines.models import Machine
    from tests.machines.certification_helpers import _machine_type, _member

    space = _space("supervised-events-off", modules=("machines", "membership", "member_accounts"),
                   features=("machines.supervised_sessions",))
    machine = Machine.objects.create(makerspace=space, machine_type=_machine_type(space), name="Lathe")
    instructor, _membership = _member(space, "supervised-instructor")
    response = authenticated_client(instructor).post(
        reverse("member-supervised-session-open", kwargs={"machine_id": machine.pk}), {"event_id": 1}, format="json")
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "module_disabled" and response.json()["module"] == "events"


def test_organization_names_are_hidden_while_organization_bookings_are_off(monkeypatch):
    from apps.bookings import organization_booking

    space_on = _space("org-names-on", features=("bookings.organization_bookings",))
    space_off = _space("org-names-off")
    rows = [SimpleNamespace(booking_id=1, organization_name="Robotics club", makerspace_id=space_on.pk,
                            makerspace=space_on),
            SimpleNamespace(booking_id=2, organization_name="Chess club", makerspace_id=space_off.pk,
                            makerspace=space_off)]

    class _Query(list):
        def select_related(self, *_args):
            return self

    monkeypatch.setattr(organization_booking.BookingOrganizationLink.objects, "filter",
                        lambda **_kwargs: _Query(rows))
    assert organization_booking.organization_names([1, 2]) == {1: "Robotics club"}


@pytest.mark.parametrize("view_name,modules,features", (
    ("guest_passes", ("membership",), ("membership.guest_passes",)),
    ("day_pass_products", ("membership",), ("membership.day_passes", "membership.guest_passes")),
    ("guest_certification_grants", ("events", "machines"), ("machines.induction_events",)),
    ("incidents", (), ("safety.incidents",)),
    ("incident_actions", (), ("safety.incidents",)),
    ("included_hours_usage", ("bookings", "membership"), ()),
    ("loan_event_contexts", ("events",), ()),
    ("events", ("events",), ()),
    ("event_orders", ("events",), ()),
    ("shop_orders", ("shop",), ()),
    ("sponsors", (), ("finance.sponsors",)),
    ("membership_plans", ("membership",), ()),
    ("members", (), ()),
    ("payments", (), ()),
))
def test_analytics_views_follow_their_area_switch(view_name, modules, features):
    from apps.analytics.catalogue.registry import all_views
    from apps.analytics.catalogue.render import SPACE, render, switch_keys

    view = next(row for row in all_views() if row.name == view_name)
    assert switch_keys(view) == (sorted(modules), sorted(features))
    sql = render(view, SPACE)
    for module in modules:
        assert f"enabled_modules ? '{module}'" in sql
    for feature in features:
        assert f"enabled_features ? '{feature}'" in sql
    assert "enabled_modules ? 'analytics'" in sql
