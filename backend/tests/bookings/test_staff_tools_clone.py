"""Resource clones copy owned configuration/assets without authority or history."""

from unittest.mock import Mock

import pytest
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.bookings import services, storage
from apps.bookings.models import BookableSpace, BookingCalendarFeed, BookingSpaceStaffGrant
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import limits
from apps.payments.models import Payment
from tests.bookings.test_staff_tools_helpers import full_manager, world
from tests.machines.certification_helpers import _machine_type, _space

pytestmark = pytest.mark.django_db(transaction=True)


def cover(monkeypatch, w, *, size=123, cap=10000):
    key = storage.owned_prefix(w.resource) + "original.png"
    w.resource.image_key = key
    w.resource.save(update_fields=["image_key"])
    objects = {key: size}
    def copy(source, destination):
        objects[destination] = objects[source]
    def delete(key):
        objects.pop(key, None)
        return True
    copied, deleted = Mock(side_effect=copy), Mock(side_effect=delete)
    monkeypatch.setattr(storage, "object_size", lambda key: objects.get(key))
    monkeypatch.setattr(storage, "copy_object", copied)
    monkeypatch.setattr(storage, "delete_object", deleted)
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(limits, "resource_limit", lambda tenant, kind: cap if kind == "storage" else None)
    return key, objects, copied, deleted


def test_clone_has_fresh_identity_private_defaults_and_no_authority_or_history(monkeypatch):
    w = world(monkeypatch, charged=True)
    source = w.resource
    source.is_public = source.show_public_availability = source.show_public_booker_names = True
    source.description, source.location, source.capacity = "Resource description", "Main lab", 8
    source.booking_lead_time_minutes, source.cancellation_cutoff_hours = 180, 4
    source.requester_notifications_enabled = False
    source.save()
    feed = BookingCalendarFeed.objects.create(makerspace=w.tenant, user=w.member,
                                              token_digest=b"a" * 32, token_hint="a" * 8)
    key, objects, copied, deleted = cover(monkeypatch, w)
    clone = services.clone_space(source, actor=w.actor)
    assert clone.pk != source.pk and clone.public_token != source.public_token
    assert clone.name == source.name + " (copy)" and clone.created_by == w.actor
    assert clone.is_active and not clone.is_public and not clone.show_public_availability and not clone.show_public_booker_names
    assert (clone.description, clone.location, clone.capacity, clone.custom_form, clone.payment_amount) == (
        source.description, source.location, source.capacity, source.custom_form, source.payment_amount,
    )
    assert clone.requester_notifications_enabled is False
    defaults = BookableSpace()
    from apps.bookings.services_rules import RULE_FIELDS
    assert all(getattr(clone, field) == getattr(defaults, field) for field in RULE_FIELDS)
    assert clone.image_key != key and clone.image_key.startswith(storage.owned_prefix(clone))
    assert objects[clone.image_key] == objects[key] and copied.call_count == 1 and not deleted.called
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == 123
    assert not clone.bookings.exists() and not BookingSpaceStaffGrant.objects.filter(space=clone).exists()
    assert BookingCalendarFeed.objects.count() == 1 and BookingCalendarFeed.objects.get().pk == feed.pk
    assert Payment.objects.count() == 1 and Payment.objects.get().subject_id == w.row.pk
    audit = AuditLog.objects.get(action="booking.space_cloned")
    assert audit.actor == w.actor and audit.meta == {"source_space_id": source.pk, "copy_booking_rules": False}


def test_booking_manager_copies_exact_rules(monkeypatch):
    # Fixed roles: booking rules belong to the Booking Manager (MANAGE_BOOKINGS), so the
    # tenant manager who may clone may also copy them; no MANAGE_MAKERSPACE is needed.
    w = world(monkeypatch)
    w.resource.cancellation_cutoff_hours = 7
    w.resource.buffer_before_minutes = 13
    w.resource.save(update_fields=["cancellation_cutoff_hours", "buffer_before_minutes"])
    clone = services.clone_space(w.resource, actor=w.actor, copy_booking_rules=True)
    from apps.bookings.services_rules import RULE_FIELDS
    assert all(getattr(clone, field) == getattr(w.resource, field) for field in RULE_FIELDS)


@pytest.mark.parametrize("value", ["yes", 1, None, [], {}])
def test_service_does_not_coerce_protected_copy_flag(monkeypatch, value):
    w = world(monkeypatch)
    with pytest.raises(ValidationError):
        services.clone_space(w.resource, actor=w.actor, copy_booking_rules=value)
    assert BookableSpace.objects.count() == 1


@pytest.mark.parametrize("foreign", [False, True])
def test_clone_revalidates_machine_link_tenant_ownership(monkeypatch, foreign):
    w = world(monkeypatch)
    machine_type = _machine_type(_space("foreign-machine") if foreign else w.tenant)
    w.resource.machine_type = machine_type
    w.resource.save(update_fields=["machine_type"])
    if foreign:
        with pytest.raises(ValidationError):
            services.clone_space(w.resource, actor=w.actor)
        assert BookableSpace.objects.count() == 1
    else:
        assert services.clone_space(w.resource, actor=w.actor).machine_type_id == machine_type.pk


def test_clone_refuses_machine_link_when_machine_module_has_been_removed(monkeypatch):
    w = world(monkeypatch)
    w.resource.machine_type = _machine_type(w.tenant)
    w.resource.save(update_fields=["machine_type"])
    w.tenant.enabled_modules.remove("machines")
    w.tenant.save(update_fields=["enabled_modules"])
    from apps.makerspaces.guards import SurfaceOff
    with pytest.raises((ValidationError, SurfaceOff)):  # #183B: a module that is off answers with its typed 404
        services.clone_space(w.resource, actor=w.actor)
    assert BookableSpace.objects.count() == 1


@pytest.mark.parametrize("failure", ["quota", "missing", "oversize", "foreign_key", "copy_timeout", "verification", "audit"])
def test_cover_failure_rolls_back_resource_quota_and_cleans_only_fresh_objects(monkeypatch, settings, failure):
    w = world(monkeypatch)
    key, objects, copied, deleted = cover(monkeypatch, w, cap=122 if failure == "quota" else 10000)
    baseline = AuditLog.objects.count()
    if failure == "missing":
        objects.pop(key)
    elif failure == "oversize":
        settings.PUBLIC_IMAGE_MAX_BYTES = 122
    elif failure == "foreign_key":
        w.resource.image_key = f"spaces/{w.tenant.pk}/999999/images/foreign.png"
        w.resource.save(update_fields=["image_key"])
    elif failure in {"copy_timeout", "verification"}:
        def broken_copy(source, target):
            objects[target] = objects[source] + (1 if failure == "verification" else 0)
            if failure == "copy_timeout":
                raise StorageUnavailable("copy outcome unknown")
        copied.side_effect = broken_copy
    elif failure == "audit":
        def failed_audit(*args, **kwargs):
            raise RuntimeError("audit insert failed")
        monkeypatch.setattr("apps.bookings.services_bookings.audit.record", failed_audit)
    with pytest.raises((ValidationError, StorageUnavailable, RuntimeError)):
        services.clone_space(w.resource, actor=w.actor)
    assert BookableSpace.objects.count() == 1 and AuditLog.objects.count() == baseline
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == 0
    assert set(objects) <= {key}
    assert all(call.args[0] != key for call in deleted.call_args_list)
    assert deleted.call_count == (1 if failure in {"copy_timeout", "verification", "audit"} else 0)


def test_two_clones_have_independent_deletable_cover_objects(monkeypatch):
    w = world(monkeypatch)
    key, objects, copied, deleted = cover(monkeypatch, w)
    first = services.clone_space(w.resource, actor=w.actor)
    second = services.clone_space(w.resource, actor=w.actor)
    assert len({key, first.image_key, second.image_key}) == 3
    storage.delete_object(first.image_key)
    assert key in objects and second.image_key in objects


def test_clone_requires_own_commit_boundary_before_copying_any_asset(monkeypatch):
    w = world(monkeypatch)
    _, objects, copied, deleted = cover(monkeypatch, w)
    with transaction.atomic():
        with pytest.raises(RuntimeError, match="durable"):
            services.clone_space(w.resource, actor=w.actor)
    assert BookableSpace.objects.count() == 1 and not copied.called and not deleted.called


def test_later_website_clone_adapter_joins_the_same_transaction_and_asset_cleanup(monkeypatch):
    from apps.makerspaces import resource_clone_extensions
    w = world(monkeypatch)
    key, objects, copied, deleted = cover(monkeypatch, w)
    observed = []
    def website_copy(source, clone, assets):
        observed.append((source.pk, clone.pk, len(assets.created)))
        assert clone.is_public is False and clone.pk != source.pk
        raise ValidationError("Website cannot be copied")
    monkeypatch.setattr(resource_clone_extensions, "_extensions", {})
    resource_clone_extensions.register_clone_extension("bookings", "website", website_copy)
    with pytest.raises(ValidationError, match="Website cannot be copied"):
        services.clone_space(w.resource, actor=w.actor)
    assert observed and observed[0][0] == w.resource.pk and observed[0][2] == 1
    assert BookableSpace.objects.count() == 1 and set(objects) == {key}
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == 0 and copied.call_count == deleted.call_count == 1
