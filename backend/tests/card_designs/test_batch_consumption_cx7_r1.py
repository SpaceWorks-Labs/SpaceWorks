"""A matched batch consumes its original allocation; only confirmed absence releases debt."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.card_designs import photo_batch, photo_batch_apply
from apps.card_designs.images import normalise
from apps.card_designs.models_cutout import CardPhotoBatch
from apps.card_designs.models_staff_cards import StaffCard
from apps.events.models import Event, EventIdCard, EventRegistration
from apps.makerspaces.models import StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import sweep
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.events.test_cover_reservations_cx7_r1 import Objects, png
from tests.l3_local.helpers import card_event, card_space, issue, manager, member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_membership, pytest.mark.area_events]


def world(kind, settings, monkeypatch, *, key="storage"):
    settings.MANAGED_PLANS_ENABLED = False
    space = card_space("r1-batch", features=("membership.staff_cards", "events.id_cards"))
    actor = manager(space)
    person, membership = member(space)
    target = issue(space, membership, by=actor)
    event = None
    if kind == "staff_card":
        from tests.fixed_roles.helpers import assign_builtin_roles
        staff_membership = assign_builtin_roles(person, space, "inventory_manager")
        assert staff_membership.pk != membership.pk
        holder = StaffCard.objects.create(makerspace=space, membership=staff_membership, card_number=1)
        filename = "S-0001.png"
    elif kind == "event_card":
        event = card_event(space)
        registration = EventRegistration.objects.create(event=event, member=person, name="Holder", email=person.email)
        target = EventIdCard.objects.create(makerspace=space, event=event, registration=registration, person=person,
            printed_name="Holder", valid_until=event.ends_at + timedelta(days=1))
        holder, filename = target, "Holder.png"
    else:
        target.number_text = "MEM-0001"
        target.save(update_fields=["number_text"])
        holder, filename = target, "MEM-0001.png"
    data = png()
    normalized = normalise(data, max_edge=1200, keep_alpha=False)[0]
    space.resource_limit_overrides = {key: len(normalized)}
    space.save(update_fields=["resource_limit_overrides"])
    objects = Objects()
    monkeypatch.setattr("apps.evidence.storage._client", lambda: objects)
    monkeypatch.setattr("apps.object_storage.delete_all_versions", objects.delete)
    batch = photo_batch.create(actor, space, kind, event, holders_consented=True, remove_backgrounds=False)
    assert photo_batch.add_files(batch, space, event, [SimpleUploadedFile(filename, data, content_type="image/png")]) == 0
    item = batch.items.get()
    assert (item.holder_id, item.decision) == (holder.pk, "apply")
    assert reserved_bytes(space) == len(normalized)
    return space, actor, target, batch, item, objects, normalized


@pytest.mark.parametrize("kind", ["member_card", "staff_card", "event_card"])
@pytest.mark.parametrize("key", ["storage", "storage_public_images_bytes"])
def test_matched_holder_applies_at_cap_without_a_second_allocation(kind, key, settings, monkeypatch):
    space, actor, target, batch, item, objects, normalized = world(kind, settings, monkeypatch, key=key)
    CardPhotoBatch.objects.filter(pk=batch.pk).update(state="applying")
    assert photo_batch_apply.apply_chunk(batch.pk) is False
    target.refresh_from_db()
    space.refresh_from_db()
    batch.refresh_from_db()
    assert batch.applied_count == 1
    assert (batch.failed_count, batch.skipped_count) == (0, 0)
    assert target.photo_size_bytes == len(normalized)
    assert objects.values[settings.AWS_STORAGE_BUCKET_NAME, target.photo_object_key][0] == normalized
    assert (settings.AWS_STORAGE_BUCKET_NAME, item.file_key) not in objects.values
    assert (space.storage_bytes_used, reserved_bytes(space)) == (len(normalized), 0)
    receipt = StorageQuotaReservation.objects.get(object_key=item.file_key)
    assert (receipt.converted, receipt.released, receipt.final_key) == (True, True, target.photo_object_key)
    assert AuditLog.objects.filter(action="card_photo_batch.item_applied", makerspace=space).count() == 1
    action = "event_card.photo_updated" if kind == "event_card" else "member_card.photo_updated"
    assert AuditLog.objects.filter(action=action, makerspace=space).count() == 1


@pytest.mark.parametrize("kind", ["member_card", "staff_card", "event_card"])
def test_cancellation_at_cap_releases_only_confirmed_bytes_and_allows_a_fitting_upload(kind, settings, monkeypatch):
    space, actor, target, batch, item, objects, normalized = world(kind, settings, monkeypatch)
    photo_batch.cancel(actor, batch, space)
    assert (reserved_bytes(space), len(objects.values)) == (0, 0)
    target.refresh_from_db()
    space.refresh_from_db()
    assert (target.photo_object_key, space.storage_bytes_used) == ("", 0)
    assert StorageQuotaReservation.objects.get(object_key=item.file_key).released is True
    event = Event.objects.get(pk=batch.event_id) if kind == "event_card" else None
    next_batch = photo_batch.create(actor, space, kind, event, holders_consented=True, remove_backgrounds=False)
    assert photo_batch.add_files(next_batch, space, event,
        [SimpleUploadedFile(item.filename + ".png", png(), content_type="image/png")]) == 0
    assert reserved_bytes(space) == len(normalized)
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=space).count() == 1


def test_failed_cancellation_delete_retains_debt_and_a_prompt_retry_receipt(settings, monkeypatch):
    from types import SimpleNamespace
    space, actor, target, batch, item, objects, normalized = world("member_card", settings, monkeypatch)
    monkeypatch.setattr("apps.object_storage.delete_all_versions",
                        lambda *args, **kwargs: SimpleNamespace(absence_confirmed=False))
    photo_batch.cancel(actor, batch, space)
    receipt = StorageQuotaReservation.objects.get(object_key=item.file_key)
    assert receipt.released is False
    assert receipt.expires_at <= timezone.now()
    assert reserved_bytes(space) == len(normalized)
    assert batch.items.get().file_key == item.file_key
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=space).count() == 0
    event = None
    next_batch = photo_batch.create(actor, space, "member_card", event, holders_consented=True, remove_backgrounds=False)
    with pytest.raises(APIException) as refused:
        photo_batch.add_files(next_batch, space, event, [SimpleUploadedFile("MEM-0001.png", png())])
    assert (refused.value.status_code, str(refused.value.detail["code"])) == (400, "limit_reached")
    monkeypatch.setattr("apps.object_storage.delete_all_versions", objects.delete)
    assert sweep() == 1
    assert (reserved_bytes(space), len(objects.values)) == (0, 0)
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=space).count() == 1


@pytest.mark.parametrize("kind", ["member_card", "staff_card", "event_card"])
def test_failed_source_deletion_cannot_convert_or_attach_a_batch_photo(kind, settings, monkeypatch):
    from types import SimpleNamespace
    space, actor, target, batch, item, objects, normalized = world(kind, settings, monkeypatch)
    monkeypatch.setattr("apps.object_storage.delete_all_versions",
                        lambda *args, **kwargs: SimpleNamespace(absence_confirmed=False))
    CardPhotoBatch.objects.filter(pk=batch.pk).update(state="applying")
    assert photo_batch_apply.apply_chunk(batch.pk) is False
    target.refresh_from_db()
    space.refresh_from_db()
    receipt = StorageQuotaReservation.objects.get(object_key=item.file_key)
    assert (target.photo_object_key, space.storage_bytes_used) == ("", 0)
    assert (receipt.converted, receipt.released, reserved_bytes(space)) == (False, False, len(normalized))
    assert objects.values[settings.AWS_STORAGE_BUCKET_NAME, item.file_key][0] == normalized
    assert batch.items.get().error_code == "apply_failed"
    assert AuditLog.objects.filter(action="card_photo_batch.item_applied", makerspace=space).count() == 0


def test_multifile_compensation_confirms_deletion_before_releasing_its_debt(settings, monkeypatch):
    space, actor, target, batch, item, objects, normalized = world("member_card", settings, monkeypatch)
    photo_batch.cancel(actor, batch, space)
    fresh = photo_batch.create(actor, space, "member_card", None, holders_consented=True, remove_backgrounds=False)
    with pytest.raises(APIException) as refused:
        photo_batch.add_files(fresh, space, None, [SimpleUploadedFile(name, png()) for name in ("one.png", "two.png")])
    assert (refused.value.status_code, str(refused.value.detail["code"])) == (400, "limit_reached")
    assert fresh.items.count() == 0
    assert (reserved_bytes(space), len(objects.values)) == (0, 0)
    assert StorageQuotaReservation.objects.filter(makerspace=space, released=True).count() == 2
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=space).count() == 2


def test_deleting_a_batch_settles_its_temporary_receipt_after_commit(settings, monkeypatch):
    space, actor, target, batch, item, objects, normalized = world("member_card", settings, monkeypatch)
    batch.delete()
    assert StorageQuotaReservation.objects.get(object_key=item.file_key).released is True
    assert (reserved_bytes(space), len(objects.values)) == (0, 0)
    assert AuditLog.objects.filter(action="storage.upload_reservation_released", makerspace=space).count() == 1


@pytest.mark.parametrize("kind", ["member_card", "staff_card", "event_card"])
def test_batch_destination_claim_survives_a_resumed_attachment_rollback(kind, settings, monkeypatch):
    from django.db import IntegrityError, transaction
    from apps.audit import services as audit
    from apps.makerspaces.storage_reservation_cleanup import cleanup
    space, actor, target, batch, item, objects, normalized = world(kind, settings, monkeypatch)
    receipt = StorageQuotaReservation.objects.get(object_key=item.file_key)
    claimed_key = receipt.final_key
    assert claimed_key != item.file_key
    original_record = audit.record
    def fail(*args, **kwargs):
        raise IntegrityError("injected batch attachment audit failure")
    monkeypatch.setattr(audit, "record", fail)
    holder = photo_batch.roster.load_card(kind, space, item.holder_id,
        Event.objects.get(pk=batch.event_id) if batch.event_id else None)
    with pytest.raises(IntegrityError, match="injected batch attachment audit failure"):
        with transaction.atomic():
            photo_batch_apply._attach(actor, kind, holder, normalized, item.file_key)
    receipt.refresh_from_db()
    assert (receipt.final_key, receipt.converted, reserved_bytes(space)) == (claimed_key, False, len(normalized))
    assert objects.values[settings.AWS_STORAGE_BUCKET_NAME, claimed_key][0] == normalized
    target.refresh_from_db()
    assert target.photo_object_key == ""
    monkeypatch.setattr(audit, "record", original_record)
    assert cleanup(receipt.pk, now=receipt.expires_at + timedelta(seconds=1)) is True
    assert (reserved_bytes(space), len(objects.values)) == (0, 0)
