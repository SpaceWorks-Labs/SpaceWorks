"""Release 0.12.0 module on/off audit (#95, #183B, #197, #216).

Every new cross-module route answers the typed 404 `module_disabled` naming the module
that is off, the ordinary neighbouring route keeps working, retained rows survive the
switch, and switching the module back on restores the surface with the same data.
Ordinary settings profile; the deployment tombstone profile lives in `tests/tombstone`.
"""

import pytest
from django.urls import resolve, reverse

from apps.accounts.models import User
from apps.makerspaces.module_install import install_module
from tests.events.checkin_helpers import make_event
from tests.module_helpers import disable_module
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

NEEDED = ("events", "bookings", "machines", "shop")

# (url name, needs a real event, module switched off, module the 404 must name)
EVENT_ROUTES = (
    ("finance-event-linked", False, "events", "events"),
    ("admin-event-booking-link", False, "events", "events"),
    ("admin-event-booking-link", False, "bookings", "bookings"),
    ("admin-event-workshop-machines", False, "events", "events"),
    ("admin-event-workshop-machines", False, "bookings", "bookings"),
    ("admin-event-workshop-machines", True, "machines", "machines"),
    ("event-equipment-desk", True, "events", "events"),
    ("event-equipment-request-products", True, "events", "events"),
    ("event-equipment-kits", True, "events", "events"),
    ("admin-related-facts-event", True, "events", "events"),
)

# Every new route must resolve in the ordinary profile; optional-domain routes must live in
# that domain's own urlconf so a deployment tombstone removes them with the app.
NEW_ROUTE_OWNERS = {
    "admin-event-booking-link": "apps.events", "admin-event-booking-replacement": "apps.events",
    "admin-event-workshop-machines": "apps.events", "event-equipment-desk": "apps.events",
    "event-equipment-request-products": "apps.events", "event-equipment-kits": "apps.events",
    "admin-request-event-context": "apps.events", "member-event-equipment": "apps.events",
    "admin-request-booking-context": "apps.bookings", "booking-equipment-request-products": "apps.bookings",
    "booking-equipment-kits": "apps.bookings", "admin-space-booking-quote": "apps.bookings",
    "admin-space-booking-readiness": "apps.bookings", "admin-space-booking-availability": "apps.bookings",
    "admin-booking-readiness": "apps.bookings", "admin-shop-event-offers": "apps.shop",
    "public-shop-event-offers": "apps.shop", "admin-loan-repairs": "apps.maintenance",
    "notifications:browser-firebase-config": "apps.notifications",
}


def _space(slug):
    space = make_space(slug)
    for key in NEEDED:
        install_module(space, key)
    space.refresh_from_db()
    return space


def _assert_off(response, module):
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "module_disabled", response.content
    assert response.json()["module"] == module


@pytest.mark.parametrize("name", sorted(NEW_ROUTE_OWNERS))
def test_new_route_lives_in_its_owning_app(name):
    kwargs = {key: 1 for key in ("makerspace_id", "event_id", "request_id", "loan_id", "space_id", "pk")}
    for candidate in (kwargs, {"makerspace_id": 1, "event_id": 1}, {"makerspace_id": 1, "request_id": 1},
                      {"makerspace_id": 1, "space_id": 1}, {"pk": 1}, {"makerspace_id": 1, "pk": 1},
                      {"makerspace_id": 1}, {"makerspace_slug": "s", "public_token": "00000000-0000-0000-0000-000000000000"}):
        try:
            path = reverse(name, kwargs=candidate)
            break
        except Exception:  # noqa: BLE001 -- probing the route's own kwarg shape
            continue
    else:
        pytest.fail(f"{name} does not reverse")
    func = resolve(path).func
    owner = getattr(func, "view_class", func).__module__
    assert owner.startswith(NEW_ROUTE_OWNERS[name] + "."), (name, owner)


@pytest.mark.django_db
@pytest.mark.parametrize("name,needs_event,off,named", EVENT_ROUTES)
def test_event_cross_module_route_answers_typed_404_when_a_module_is_off(name, needs_event, off, named):
    space = _space(f"rel0120-{name[:18]}-{off}")
    manager = make_member(f"rel0120-sm-{name[:14]}-{off}", space)
    event = make_event(space)
    disable_module(space, off)
    event_id = event.pk if needs_event else 999999
    response = authenticated_client(manager).get(
        reverse(name, kwargs={"makerspace_id": space.pk, "event_id": event_id}))
    _assert_off(response, named)


# m11 remainder (221b): the window, bulk-plan and workshop-machine unlink routes follow the events switch too.
EXTRA_EVENT_ROUTES = (
    ("event-equipment-availability", "get", {}),
    ("event-equipment-plan", "post", {}),
    ("admin-event-workshop-machine-link", "delete", {"link_id": 1}),
)


@pytest.mark.django_db
@pytest.mark.parametrize("name,method,extra", EXTRA_EVENT_ROUTES)
def test_equipment_window_plan_and_unlink_routes_answer_typed_404_with_events_off(name, method, extra):
    space = _space(f"rel0120-xr-{name[-12:]}")
    manager = make_member(f"rel0120-xr-sm-{name[-10:]}", space)
    event = make_event(space)
    disable_module(space, "events")
    response = getattr(authenticated_client(manager), method)(
        reverse(name, kwargs={"makerspace_id": space.pk, "event_id": event.pk, **extra}), data={}, format="json")         if method != "get" else authenticated_client(manager).get(
            reverse(name, kwargs={"makerspace_id": space.pk, "event_id": event.pk, **extra}))
    _assert_off(response, "events")


@pytest.mark.django_db
def test_member_event_equipment_answers_typed_404_with_events_off():
    space = _space("rel0120-member-equipment")
    member = make_user("rel0120-member-equipment-user", access_status=User.AccessStatus.ACTIVE)
    disable_module(space, "events")
    response = authenticated_client(member).get(
        reverse("member-event-equipment", kwargs={"makerspace_id": space.pk, "pk": 999999}))
    _assert_off(response, "events")


@pytest.mark.django_db
def test_workshop_machine_link_is_kept_off_and_restored_on_re_enable():
    from apps.events.models_machine_booking_link import EventMachineBookingLink

    space = _space("rel0120-workshop-reenable")
    manager = make_member("rel0120-workshop-sm", space)
    event = make_event(space)
    link = EventMachineBookingLink.objects.create(makerspace=space, event=event, booking=None)
    url = reverse("admin-event-workshop-machines", kwargs={"makerspace_id": space.pk, "event_id": event.pk})
    client = authenticated_client(manager)

    disable_module(space, "machines")
    _assert_off(client.get(url), "machines")
    assert EventMachineBookingLink.objects.filter(pk=link.pk).exists()

    install_module(space, "machines")
    restored = client.get(url)
    assert restored.status_code == 200, restored.content
    rows = restored.json()["results"]
    assert [row["link_id"] for row in rows] + [None] * restored.json()["withheld"] in ([link.pk], [None])


@pytest.mark.django_db
def test_linked_finance_events_off_is_typed_and_ordinary_finance_survives():
    space = _space("rel0120-finance-off")
    manager = make_member("rel0120-finance-sm", space)
    event = make_event(space)
    disable_module(space, "events")
    client = authenticated_client(manager)
    _assert_off(client.get(reverse("finance-event-linked", kwargs={"makerspace_id": space.pk, "event_id": event.pk})),
                "events")
    install_module(space, "events")
    restored = client.get(reverse("finance-event-linked", kwargs={"makerspace_id": space.pk, "event_id": event.pk}))
    # Back on: no longer the module-off answer (an event with no visible section is a plain 404).
    assert restored.status_code in (200, 404)
    assert restored.status_code == 200 or restored.json().get("code") != "module_disabled"


@pytest.mark.django_db
def test_shop_event_offers_hide_with_events_off_and_return_on_re_enable():
    from tests.shop.helpers import shop_space, switch

    space = switch(shop_space("rel0120-shop-offers", "shop.online", "shop.event_pickup"), modules=("events",))
    manager = make_member("rel0120-shop-sm", space)
    url = reverse("admin-shop-event-offers", kwargs={"makerspace_id": space.pk})
    client = authenticated_client(manager)
    assert client.get(url).status_code == 200

    disable_module(space, "events")
    hidden = client.get(url)
    assert hidden.status_code == 404 and hidden.json()["feature"] == "events"

    # Uninstalling Events uninstalls its dependents first (module_helpers), so the shop is switched back on too.
    install_module(space, "events")
    install_module(space, "shop")
    switch(space, "shop.online", "shop.event_pickup")
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_event_return_due_ignores_the_event_while_events_is_off():
    from types import SimpleNamespace

    from apps.separability.equipment_context_bridge import event_return_due

    space = _space("rel0120-due-off")
    disable_module(space, "events")
    space.refresh_from_db()
    # No query is needed to decide: Events off leaves the core loan-days policy in charge.
    assert event_return_due(SimpleNamespace(pk=1, makerspace=space, makerspace_id=space.pk), None) is None
