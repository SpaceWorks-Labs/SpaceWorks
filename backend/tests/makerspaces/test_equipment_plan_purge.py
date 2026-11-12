from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking, BookableSpace
from apps.bookings.models_consumable_plan_context import BookingConsumablePlanContext
from apps.events.models import Event
from apps.events.models_consumable_plan_context import EventConsumablePlanContext
from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentKitTemplate, EquipmentKitVersion
from apps.makerspaces.module_purge import purge_module
from apps.tenant_migration.models import ExternalTenantReference
from tests.test_request_workflow import make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("domain", ["events", "bookings"])
def test_module_purge_removes_plan_link_and_its_provenance_but_keeps_core_plan(domain):
    actor = User.objects.create_superuser(username="plan-root-" + domain)
    borrower = User.objects.create_user(username="plan-member-" + domain)
    space = make_space("plan-purge-" + domain)
    space.enabled_modules = [key for key in space.enabled_modules if key != domain]
    space.save(update_fields=["enabled_modules"])
    template = EquipmentKitTemplate.objects.create(makerspace=space, name="Materials")
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="Materials", lines=[])
    plan = EquipmentConsumablePlan.objects.create(makerspace=space, borrower=borrower, kit_version=version, lines=[])
    start = timezone.now() + timedelta(days=2)
    if domain == "events":
        event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
        context = EventConsumablePlanContext.objects.create(makerspace=space, plan=plan, event=event)
    else:
        room = BookableSpace.objects.create(makerspace=space, name="Room")
        booking = Booking.objects.create(space=room, name="Member", email="m@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
        context = BookingConsumablePlanContext.objects.create(makerspace=space, plan=plan, booking=booking)
    def reference(label, source):
        return ExternalTenantReference.objects.create(makerspace=space, source_archive_digest="a" * 64, source_model_label="events.EventCollaborator", source_object_id=source, field_name="event", target_model_label=label, target_object_id=str(context.pk), snapshot={"title": "Event", "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()})
    own = reference(context._meta.label, "1")
    other = reference("inventory.InventoryProduct", "2")
    purge_module(space, domain, actor)
    assert not type(context).objects.filter(pk=context.pk).exists()
    assert EquipmentConsumablePlan.objects.filter(pk=plan.pk).exists()
    assert not ExternalTenantReference.objects.filter(pk=own.pk).exists()
    assert ExternalTenantReference.objects.filter(pk=other.pk).exists()
