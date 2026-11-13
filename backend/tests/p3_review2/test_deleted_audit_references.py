import json

import pytest

from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace
from apps.bookings.models_gallery import BookableSpacePhoto
from apps.bookings.services_gallery import delete_photo, update_photo
from apps.data_export.reference_provenance import ReferenceProvenanceWriter
from apps.events.models import EventCategory, EventTicketType
from apps.events.ticketing_edit import delete_category, delete_ticket, update_category, update_ticket
from apps.tenant_migration.semantic_remap import _remap_audit
from tests.p2_events.helpers import event, make_staff, space

pytestmark = pytest.mark.django_db


class NoDeletedMappings:
    def lookup(self, model, value):
        assert model not in {EventCategory, EventTicketType, BookableSpacePhoto}, "Deleted IDs must stay inert"
        return int(value) + 1000


def project_and_import(tmp_path, home, rows):
    writer = ReferenceProvenanceWriter(tmp_path, home.pk)
    try:
        writer.prepare_rows("audit.AuditLog", rows)
        projected = []
        for log in rows:
            row = {"actor_id": log.actor_id, "action": log.action,
                   **{field: writer.project(log, field, getattr(log, field))
                      for field in ("target_type", "target_id", "meta")}}
            _remap_audit(row, NoDeletedMappings())
            projected.append(row)
    finally:
        writer.close()
    return projected, [json.loads(line) for line in writer.path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("kind", ["ticket", "category"])
def test_deleted_ticket_and_category_history_projects_and_imports_without_pk_mapping(tmp_path, kind):
    home = space("deleted-" + kind)
    actor = make_staff(home)
    if kind == "ticket":
        target = EventTicketType.objects.create(makerspace=home, event=event(home), name="Unused")
        edit, delete = update_ticket, delete_ticket
    else:
        target = EventCategory.objects.create(makerspace=home, name="Unused", slug="unused")
        edit, delete = update_category, delete_category
    pk = target.pk
    audit.record(actor, f"event.{kind}_created", makerspace=home, target=target)
    edit(target, actor=actor, name="Renamed")
    delete(target, actor=actor)
    assert not type(target).objects.filter(pk=pk).exists()
    rows = list(AuditLog.objects.filter(makerspace=home, target_id=str(pk),
                                       target_type=target._meta.label_lower).order_by("pk"))
    assert {row.action for row in rows} == {f"event.{kind}_{action}" for action in ("created", "updated", "deleted")}
    imported, provenance = project_and_import(tmp_path, home, rows)
    assert all(row["target_type"] == row["target_id"] == "" and row["actor_id"] is None for row in imported)
    assert {item["source_object_id"] for item in provenance} == {str(row.pk) for row in rows}
    assert all(item["detail"]["source_target_id"] == str(pk) for item in provenance)


def test_deleted_gallery_photo_is_inert_in_added_updated_and_removed_audits(tmp_path):
    home = space("deleted-gallery")
    home.enabled_modules = sorted(set(home.enabled_modules) | {"bookings"})
    home.save(update_fields=["enabled_modules"])
    actor = make_staff(home)
    room = BookableSpace.objects.create(makerspace=home, name="Workshop")
    photo = BookableSpacePhoto.objects.create(space=room, object_key="spaces/deleted.jpg", size_bytes=0)
    pk = photo.pk
    audit.record(actor, "booking.space_photo_added", makerspace=home, target=room, meta={"photo_id": pk})
    update_photo(room, pk, actor=actor, caption="Updated")
    delete_photo(room, pk, actor=actor)
    assert not BookableSpacePhoto.objects.filter(pk=pk).exists()
    rows = list(AuditLog.objects.filter(makerspace=home, action__in=[
        "booking.space_photo_added", "booking.space_photo_updated", "booking.space_photo_removed",
    ]).order_by("pk"))
    assert len(rows) == 3
    imported, _ = project_and_import(tmp_path, home, rows)
    assert all(row["meta"]["photo_id"] == f"source:{pk}" for row in imported)
    assert all(row["target_id"] == str(room.pk + 1000) for row in imported)
