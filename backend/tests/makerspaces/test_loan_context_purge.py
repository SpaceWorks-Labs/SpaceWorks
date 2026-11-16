"""Purge ordering and token lifecycle; requires isolated PostgreSQL admission."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.accounts.models import User
from apps.bookings.models import Booking, BookableSpace
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.makerspaces import lifecycle
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_purge import purge_module
from tests.test_request_workflow import make_space, make_product, make_hardware_request

pytestmark = pytest.mark.django_db(transaction=True)


def test_event_module_purge_removes_protected_link_rotates_only_event(monkeypatch):
    actor = User.objects.create_superuser(username="context-module-root")
    space = make_space("context-module-purge")
    space.enabled_modules = [x for x in space.enabled_modules if x != "events"]
    space.save(update_fields=["enabled_modules"])
    product = make_product(space)
    req = make_hardware_request(space, product)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
    EventLoanContext.objects.create(makerspace=space, request=req, event=event, active=True)
    before = dict(space.loan_context_generations)
    purge_module(space, "events", actor)
    space.refresh_from_db()
    assert space.loan_context_generations["events"] != before["events"]
    assert space.loan_context_generations["bookings"] == before["bookings"]
    assert not EventLoanContext.objects.filter(request_id=req.pk).exists()
    assert type(req).objects.filter(pk=req.pk).exists()


@pytest.mark.parametrize("optional_tombstoned", [False, True])
def test_whole_tenant_purge_removes_active_and_inactive_links(monkeypatch, optional_tombstoned):
    actor = User.objects.create_superuser(username="context-full-root")
    space = Makerspace.objects.create(name="Context purge", slug="context-full-purge", archived_at=timezone.now())
    product = make_product(space)
    first = make_hardware_request(space, product, status="returned")
    second = make_hardware_request(space, product, status="returned")
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
    room = BookableSpace.objects.create(makerspace=space, name="Room")
    booking = Booking.objects.create(space=room, name="Member", email="member@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
    EventLoanContext.objects.create(makerspace=space, request=first, event=event, active=True)
    EventLoanContext.objects.create(makerspace=space, request=second, active=False)
    BookingLoanContext.objects.create(makerspace=space, request=first, booking=booking, active=True)
    BookingLoanContext.objects.create(makerspace=space, request=second, active=False)
    if optional_tombstoned:
        monkeypatch.setattr("apps.separability.registry.runtime_active", lambda label: label not in {"events", "bookings"})
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda _keys: None)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", lambda _keys: None)
    pk = space.pk
    lifecycle.purge(space, actor)
    assert not Makerspace.objects.filter(pk=pk).exists()
    assert not EventLoanContext.objects.filter(makerspace_id=pk).exists()
    assert not BookingLoanContext.objects.filter(makerspace_id=pk).exists()

@pytest.mark.parametrize("module,label", [("events", "events.EventLoanContext"), ("bookings", "bookings.BookingLoanContext")])
def test_module_purge_removes_context_provenance_only(module, label):
    from apps.tenant_migration.models import ExternalTenantReference
    actor = User.objects.create_superuser(username="provenance-" + module)
    space = make_space("provenance-" + module)
    space.enabled_modules = [key for key in space.enabled_modules if key != module]
    space.save(update_fields=["enabled_modules"])
    req = make_hardware_request(space, make_product(space))
    start = timezone.now() + timedelta(days=2)
    if module == "events":
        event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
        row = EventLoanContext.objects.create(makerspace=space, request=req, event=event, active=True)
    else:
        room = BookableSpace.objects.create(makerspace=space, name="Room")
        booking = Booking.objects.create(space=room, name="Member", email="member@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
        row = BookingLoanContext.objects.create(makerspace=space, request=req, booking=booking, active=True)
    def reference(target, source):
        return ExternalTenantReference.objects.create(makerspace=space, source_archive_digest="a" * 64,
            source_model_label="events.EventCollaborator", source_object_id=source, field_name="event",
            target_model_label=target, target_object_id=str(row.pk), snapshot={"title": "Shared Build Night",
                "starts_at": "2026-08-20T18:00:00+00:00", "ends_at": "2026-08-20T20:00:00+00:00"})
    linked, unrelated = reference(label, "1"), reference("inventory.InventoryProduct", "2")
    purge_module(space, module, actor)
    assert not ExternalTenantReference.objects.filter(pk=linked.pk).exists()
    assert ExternalTenantReference.objects.filter(pk=unrelated.pk).exists()
    assert type(req).objects.filter(pk=req.pk).exists()
