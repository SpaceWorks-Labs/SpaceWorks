"""MOD-2: event add-on detail, sales settings and staff order routes with exact conditions."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.addons import create_addon
from apps.events.models import EventAddon, EventSalesSettings
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff, place, ticketed_event, verified
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def _addon_url(addon):
    return reverse("admin-event-addon-detail", kwargs={"pk": addon.pk})


def _settings_url(event):
    return reverse("admin-event-sales-settings", kwargs={"pk": event.pk})


def _outsider():
    return make_member("mod2-outsider", make_space("mod2-outsider-space"))


def test_addon_patch_updates_fields_and_audits_the_exact_changed_fields():
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Lunch", kind="meal", amount=Decimal("6.000"), stock=5)
    response = client_for(staff).patch(_addon_url(addon), {"name": "Late lunch", "stock": 7}, format="json")
    assert response.status_code == 200, response.content
    addon.refresh_from_db()
    assert (addon.name, addon.stock) == ("Late lunch", 7)
    row = AuditLog.objects.get(action="event.addon_updated", target_id=str(addon.pk))
    assert row.meta == {"fields": ["name", "stock"]}


def test_addon_patch_with_nothing_changed_still_returns_200_and_audits_empty_fields():
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Lunch", kind="meal", amount=Decimal("6.000"), stock=5)
    response = client_for(staff).patch(_addon_url(addon), {"stock": 5}, format="json")
    assert response.status_code == 200
    assert AuditLog.objects.get(action="event.addon_updated", target_id=str(addon.pk)).meta == {"fields": []}


def test_addon_price_is_frozen_once_an_order_line_references_it_and_delete_is_refused():
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Lunch", kind="meal", amount=Decimal("6.000"))
    buyer = verified("mod2-buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}],
                 addons=[{"addon_id": addon.pk, "quantity": 1}]).status_code == 201
    staff_client = client_for(staff)
    changed = staff_client.patch(_addon_url(addon), {"amount": "7.000"}, format="json")
    assert changed.status_code == 409 and changed.json()["code"] == "addon_referenced"
    deleted = staff_client.delete(_addon_url(addon))
    assert deleted.status_code == 409 and deleted.json()["code"] == "addon_referenced"
    addon.refresh_from_db()
    assert addon.amount == Decimal("6.000")
    assert not AuditLog.objects.filter(action="event.addon_deleted").exists()
    assert staff_client.patch(_addon_url(addon), {"is_active": False}, format="json").status_code == 200


def test_unreferenced_addon_delete_removes_it_and_audits_once():
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Kit", kind="kit", amount=Decimal("4.000"))
    assert client_for(staff).delete(_addon_url(addon)).status_code == 204
    assert not EventAddon.objects.filter(pk=addon.pk).exists()
    assert AuditLog.objects.filter(action="event.addon_deleted", target_id=str(addon.pk)).count() == 1
    assert client_for(staff).delete(_addon_url(addon)).status_code == 404


@pytest.mark.parametrize("body", [{"amount": "-1"}, {"stock": -1}, {"name": ""}, {"amount": "abc"}])
def test_addon_patch_rejects_bad_input_with_400_and_changes_nothing(body):
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Kit", kind="kit", amount=Decimal("4.000"), stock=2)
    assert client_for(staff).patch(_addon_url(addon), body, format="json").status_code == 400
    addon.refresh_from_db()
    assert (addon.name, addon.amount, addon.stock) == ("Kit", Decimal("4.000"), 2)


def test_addon_detail_refuses_signed_out_other_tenant_and_a_plain_member():
    space, event, staff, ticket = ticketed_event(amount=10)
    addon = create_addon(event, actor=staff, name="Kit", kind="kit", amount=Decimal("4.000"))
    assert APIClient().patch(_addon_url(addon), {"stock": 1}, format="json").status_code in (401, 403)
    assert client_for(_outsider()).patch(_addon_url(addon), {"stock": 1}, format="json").status_code in (403, 404)
    assert client_for(verified("mod2-plain")).delete(_addon_url(addon)).status_code in (403, 404)
    assert EventAddon.objects.filter(pk=addon.pk).exists()


def test_sales_settings_get_defaults_put_saves_and_audits_the_sorted_field_names():
    space, event, staff, ticket = ticketed_event(amount=10)
    client = client_for(staff)
    got = client.get(_settings_url(event))
    assert got.status_code == 200 and got.json()["max_tickets_per_order"] == 10
    body = {"booking_fee_fixed": "1.250", "booking_fee_bps": 250, "max_tickets_per_order": 4,
            "transfers_allowed": True, "type_changes_allowed": False, "transfer_cutoff_hours": 6}
    put = client.put(_settings_url(event), body, format="json")
    assert put.status_code == 200, put.content
    row = EventSalesSettings.objects.get(event=event)
    assert (row.booking_fee_fixed, row.booking_fee_bps, row.max_tickets_per_order, row.transfers_allowed,
            row.transfer_cutoff_hours, row.updated_by_id) == (Decimal("1.250"), 250, 4, True, 6, staff.pk)
    audit = AuditLog.objects.get(action="event.sales_settings_updated", target_id=str(event.pk))
    assert audit.meta == {"fields": sorted(body)}


@pytest.mark.parametrize(("field", "bad", "good"), [
    ("booking_fee_bps", 10001, 10000), ("max_tickets_per_order", 0, 1), ("booking_fee_fixed", "-0.001", "0.000")])
def test_sales_settings_boundaries_max_plus_one_refused_and_edge_accepted(field, bad, good):
    space, event, staff, ticket = ticketed_event(amount=10)
    client = client_for(staff)
    assert client.put(_settings_url(event), {field: bad}, format="json").status_code == 400
    assert not EventSalesSettings.objects.filter(event=event).exists()
    assert client.put(_settings_url(event), {field: good}, format="json").status_code == 200


def test_sales_settings_off_with_the_orders_capability_and_for_other_tenants():
    space, event, staff, ticket = ticketed_event(amount=10)
    assert client_for(_outsider()).get(_settings_url(event)).status_code in (403, 404)
    assert APIClient().get(_settings_url(event)).status_code in (401, 403)
    space.enabled_features = [k for k in space.enabled_features if k != "events.orders"]
    space.save(update_fields=["enabled_features"])
    for call in (client_for(staff).get, lambda url: client_for(staff).put(url, {}, format="json")):
        response = call(_settings_url(event))
        assert response.status_code == 404
    assert not EventSalesSettings.objects.filter(event=event).exists()


def test_staff_order_list_and_detail_scope_by_event_and_tenant():
    space, event, staff, ticket = ticketed_event(amount=10)
    buyer = verified("mod2-order-buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code == 201
    listing = client_for(staff).get(reverse("admin-event-orders", kwargs={"pk": event.pk}))
    assert listing.status_code == 200 and listing.json()["count"] == 1
    order_id = listing.json()["results"][0]["id"]
    detail = client_for(staff).get(reverse("admin-event-order-detail", kwargs={"pk": order_id}))
    assert detail.status_code == 200 and detail.json()["id"] == order_id
    stranger = client_for(_outsider())
    assert stranger.get(reverse("admin-event-orders", kwargs={"pk": event.pk})).status_code in (403, 404)
    assert stranger.get(reverse("admin-event-order-detail", kwargs={"pk": order_id})).status_code in (403, 404)
    assert client_for(buyer).get(reverse("admin-event-order-detail", kwargs={"pk": order_id})).status_code in (403, 404)
    space.enabled_features = [k for k in space.enabled_features if k != "events.orders"]
    space.save(update_fields=["enabled_features"])
    assert client_for(staff).get(reverse("admin-event-orders", kwargs={"pk": event.pk})).status_code == 404
