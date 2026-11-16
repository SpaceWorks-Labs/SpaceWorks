"""Hack-money G9 (add-ons for confirmed places on approval events) and G13/#181 G7 (the Space Manager's
event money settings: record-only prize tax and accepted payee pairs inside the deployment ceiling)."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.events.addons import create_addon
from apps.events.models import Event, EventOrder, EventOrderSeat, EventRegistration
from apps.payments.models import EventMoneySettings
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, order_url, ticketed_event, verified

pytestmark = pytest.mark.django_db


def approval_event(features=("events.orders", "events.addons", "events.accepted_addons")):
    space = l6_space(f"g9-{len(features)}", features=list(features))
    _space, event, staff, ticket = ticketed_event(space)
    Event.objects.filter(pk=event.pk).update(registration_requires_approval=True)
    event.refresh_from_db()
    shirt = create_addon(event, actor=staff, name="T-shirt", kind="merch", amount=Decimal(15), stock=10)
    return space, event, staff, ticket, shirt


def confirmed(event, name, status="registered"):
    member = verified(name)
    EventRegistration.objects.create(event=event, member=member, name=name, email=member.email, phone=member.phone,
                                     status=status)
    return member


def addon_order(member, event, shirt, **body):
    return client_for(member).post(order_url(event), {"tickets": [], "addons": [{"addon_id": shirt.pk, "quantity": 2}],
                                                      **body}, format="json")


# G9 -------------------------------------------------------------------------------------------

def test_a_confirmed_place_orders_add_ons_alone_and_no_seat_is_sold():
    _space, event, _staff, _ticket, shirt = approval_event()
    member = confirmed(event, "g9-confirmed")
    quoted = client_for(member).post(order_url(event, "member-event-order-quote"),
                                     {"tickets": [], "addons": [{"addon_id": shirt.pk, "quantity": 2}]}, format="json")
    assert quoted.status_code == 200, quoted.data
    assert quoted.data["seats"] == 0
    placed = addon_order(member, event, shirt)
    assert placed.status_code == 201, placed.data
    order = EventOrder.objects.get(buyer=member)
    assert order.total == Decimal("30.00") and not EventOrderSeat.objects.filter(order=order).exists()


@pytest.mark.parametrize("status", ["pending_approval", "waitlisted", "rejected", "cancelled"])
def test_an_unconfirmed_place_still_cannot_order_on_an_approval_event(status):
    _space, event, _staff, _ticket, shirt = approval_event()
    member = confirmed(event, f"g9-{status}", status=status)
    assert addon_order(member, event, shirt).data["code"] == "order_not_payable"


def test_seat_orders_stay_refused_on_approval_events_even_for_confirmed_places():
    _space, event, _staff, ticket, shirt = approval_event()
    member = confirmed(event, "g9-seat")
    response = client_for(member).post(order_url(event), {"tickets": [{"ticket_type_id": ticket.pk, "quantity": 1}],
                                                          "addons": [{"addon_id": shirt.pk, "quantity": 1}]},
                                       format="json")
    assert response.data["code"] == "order_not_payable"


def test_without_the_capability_add_on_only_orders_are_refused():
    _space, event, _staff, _ticket, shirt = approval_event(features=("events.orders", "events.addons"))
    member = confirmed(event, "g9-off")
    assert addon_order(member, event, shirt).data["code"] == "order_not_payable"


# G13 / #181 G7 ----------------------------------------------------------------------------------------

def settings_url(space):
    return reverse("admin-event-money-settings", kwargs={"makerspace_id": space.pk})


def test_event_money_settings_are_off_by_default_and_space_manager_only(settings):
    settings.EVENT_PAYOUT_TENANT_POLICIES = {}
    space, _event, staff, _ticket = ticketed_event(l6_space("g13-read"))
    body = client_for(staff).get(settings_url(space))
    assert body.status_code == 200, body.data
    assert (body.data["prize_tds_enabled"], Decimal(str(body.data["prize_tds_rate"])),
            Decimal(str(body.data["prize_tds_threshold"]))) == (False, Decimal("30.00"), Decimal("10000.00"))
    assert ["IN", "upi"] in body.data["available_payee_templates"]
    assert client_for(verified("g13-member")).get(settings_url(space)).status_code in (403, 404)


def test_the_space_narrows_payees_inside_the_ceiling_and_changes_are_audited(settings):
    from apps.audit.models import AuditLog
    from apps.payments.event_payouts.templates import configured_templates
    settings.EVENT_PAYOUT_TENANT_POLICIES = {}
    settings.EVENT_PAYOUT_TEMPLATE_CEILING = [["IN", "upi"], ["IN", "bank_transfer"]]
    space, _event, staff, _ticket = ticketed_event(l6_space("g13-write"))
    refused = client_for(staff).patch(settings_url(space), {"expected_version": 0,
                                                            "payee_templates": [["US", "bank_transfer"]]}, format="json")
    assert refused.status_code == 400
    saved = client_for(staff).patch(settings_url(space), {"expected_version": 0, "prize_tds_enabled": True,
                                                          "payee_templates": [["IN", "upi"]]}, format="json")
    assert saved.status_code == 200, saved.data
    assert {row[:2] for row in configured_templates(space.pk)[0]} == {("IN", "upi")}
    stale = client_for(staff).patch(settings_url(space), {"expected_version": 0, "prize_tds_rate": "10"}, format="json")
    assert stale.status_code == 409
    log = AuditLog.objects.filter(action="payment.event_money_settings_updated").latest("pk")
    assert sorted(log.meta["fields"]) == ["payee_templates", "prize_tds_enabled"]
    assert EventMoneySettings.objects.get(makerspace=space).version == 1


def test_an_empty_selection_keeps_the_operator_policy(settings):
    from apps.payments.event_payouts.templates import TEMPLATE_VERSION, configured_templates, template_key
    space = l6_space("g13-operator")
    policy = [["IN", "upi", template_key("IN", "upi"), TEMPLATE_VERSION]]
    settings.EVENT_PAYOUT_TENANT_POLICIES = {str(space.pk): {"templates": policy}}
    assert {row[:2] for row in configured_templates(space.pk)[0]} == {("IN", "upi")}
