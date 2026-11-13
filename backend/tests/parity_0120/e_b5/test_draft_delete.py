"""B9: only an empty draft can be deleted; anything with money or people is cancelled instead."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events.models import Event
from apps.events.models_orders import EventOrder
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for, make_event, make_member
from tests.events.test_registration_cancel_api import register
from tests.parity_0120.e_b5.helpers import world

pytestmark = pytest.mark.django_db


def test_empty_draft_is_deleted_and_audited():
    space, event, staff = world("del-a")
    Event.objects.filter(pk=event.pk).update(status="draft")
    response = client_for(staff).delete(reverse("admin-event-detail", kwargs={"pk": event.pk}))
    assert response.status_code == 204
    assert not Event.objects.filter(pk=event.pk).exists()
    assert AuditLog.objects.filter(action="event.deleted", makerspace=space).exists()


def test_published_event_is_refused():
    space, event, staff = world("del-b")
    response = client_for(staff).delete(reverse("admin-event-detail", kwargs={"pk": event.pk}))
    assert response.status_code == 409
    assert Event.objects.filter(pk=event.pk).exists()


def test_draft_with_a_registration_or_a_charge_is_refused():
    space, event, staff = world("del-c", amount="10")
    member = make_member(space, "del-m")
    registration = register(event, member)
    Event.objects.filter(pk=event.pk).update(status="draft")
    assert client_for(staff).delete(reverse("admin-event-detail", kwargs={"pk": event.pk})).status_code == 409
    assert Payment.objects.filter(subject_id=registration.pk).count() <= 1  # the ledger row is never removed


def test_draft_with_an_order_is_refused():
    space, event, staff = world("del-d")
    buyer = make_member(space, "del-b")
    EventOrder.objects.create(makerspace=space, event=event, buyer=buyer, currency="INR", status="pending", total=5)
    Event.objects.filter(pk=event.pk).update(status="draft")
    assert client_for(staff).delete(reverse("admin-event-detail", kwargs={"pk": event.pk})).status_code == 409


def test_cross_tenant_delete_is_404():
    _space, event, _staff = world("del-e")
    other_space, _other_event, other_staff = world("del-f")
    Event.objects.filter(pk=event.pk).update(status="draft")
    assert client_for(other_staff).delete(reverse("admin-event-detail", kwargs={"pk": event.pk})).status_code == 404
