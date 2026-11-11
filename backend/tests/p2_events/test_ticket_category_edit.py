"""Ticket type and event category edit/delete: audited, refused when history depends on them."""

import pytest

from apps.audit.models import AuditLog
from apps.events.models import EventCategory, EventTicketType
from tests.p2_events.helpers import account, client_for, event, make_staff, registration, space

pytestmark = pytest.mark.django_db


def _ticket(row, **values):
    return EventTicketType.objects.create(makerspace=row.makerspace, event=row, name=values.pop("name", "General"),
                                          amount=values.pop("amount", 0), **values)


def test_unused_ticket_edits_and_deletes_with_audit():
    home = space("tk-edit")
    staff, row = make_staff(home), event(home)
    ticket = _ticket(row)
    client = client_for(staff)
    patched = client.patch(f"/api/v1/admin/event-ticket-types/{ticket.pk}/", {"name": "Early bird", "amount": "5.00"}, format="json")
    assert patched.status_code == 200 and patched.data["name"] == "Early bird" and patched.data["registration_count"] == 0
    audit = AuditLog.objects.get(action="event.ticket_updated")
    assert audit.meta["fields"] == ["amount", "name"] and audit.actor == staff
    assert client.delete(f"/api/v1/admin/event-ticket-types/{ticket.pk}/").status_code == 204
    assert not EventTicketType.objects.filter(pk=ticket.pk).exists()
    assert AuditLog.objects.filter(action="event.ticket_deleted", target_id=str(ticket.pk)).exists()


def test_referenced_ticket_refuses_delete_and_price_change_but_allows_deactivation():
    home = space("tk-used")
    staff, row = make_staff(home), event(home)
    ticket = _ticket(row, capacity=5)
    sold = registration(row, account("tk-buyer"))
    sold.ticket_type = ticket
    sold.save(update_fields=["ticket_type"])
    client = client_for(staff)
    refused = client.delete(f"/api/v1/admin/event-ticket-types/{ticket.pk}/")
    assert refused.status_code == 409 and refused.data["code"] == "ticket_type_referenced"
    price = client.patch(f"/api/v1/admin/event-ticket-types/{ticket.pk}/", {"amount": "9.00"}, format="json")
    assert price.status_code == 409 and price.data["code"] == "ticket_type_referenced"
    shrink = client.patch(f"/api/v1/admin/event-ticket-types/{ticket.pk}/", {"capacity": 0}, format="json")
    assert shrink.status_code == 200  # 0 means unlimited
    low = _ticket(row, name="Limited", capacity=3)
    for name in ("tk-a", "tk-b"):
        held = registration(row, account(name))
        held.ticket_type = low
        held.save(update_fields=["ticket_type"])
    assert client.patch(f"/api/v1/admin/event-ticket-types/{low.pk}/", {"capacity": 1}, format="json").status_code == 400
    off = client.patch(f"/api/v1/admin/event-ticket-types/{ticket.pk}/", {"is_active": False}, format="json")
    assert off.status_code == 200 and off.data["is_active"] is False and off.data["registration_count"] == 1
    assert EventTicketType.objects.filter(pk=ticket.pk).exists()


def test_ticket_edit_needs_event_manager_authority():
    home = space("tk-auth")
    row = event(home)
    ticket = _ticket(row)
    stranger_staff = make_staff(space("tk-auth-other"))
    response = client_for(stranger_staff).patch(f"/api/v1/admin/event-ticket-types/{ticket.pk}/", {"name": "x"}, format="json")
    assert response.status_code in (403, 404)
    assert EventTicketType.objects.get(pk=ticket.pk).name == "General"


def test_category_rename_slug_conflict_delete_and_referenced_refusal():
    home = space("cat-edit")
    staff = make_staff(home)
    client = client_for(staff)
    base = f"/api/v1/admin/makerspaces/{home.pk}/event-categories/"
    talks = EventCategory.objects.create(makerspace=home, name="Talks", slug="talks")
    EventCategory.objects.create(makerspace=home, name="Labs", slug="labs")
    renamed = client.patch(f"{base}{talks.pk}/", {"name": "Lectures"}, format="json")
    assert renamed.status_code == 200 and renamed.data["name"] == "Lectures" and renamed.data["event_count"] == 0
    assert client.patch(f"{base}{talks.pk}/", {"slug": "labs"}, format="json").status_code == 400
    used = event(home, category=talks)
    refused = client.delete(f"{base}{talks.pk}/")
    assert refused.status_code == 409 and refused.data["code"] == "category_referenced"
    used.category = None
    used.save(update_fields=["category"])
    assert client.delete(f"{base}{talks.pk}/").status_code == 204
    assert {row.action for row in AuditLog.objects.filter(action__startswith="event.category_")} >= {
        "event.category_updated", "event.category_deleted"}
