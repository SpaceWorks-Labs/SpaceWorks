"""Purge plans for lane L16's per-parent switches (#128 C-8): repairs and item/room maintenance.

* `machines.repairs` / `inventory.repairs` / `bookings.room_repairs` delete that area's
  issue reports with their whole record (history, photos, dispatches, parts, assignments);
  photo objects are deleted after commit and their storage released.
* `inventory.maintenance` / `bookings.room_maintenance` delete that subject kind's
  schedules, logs and work orders; the room plan also deletes room outages.

The `*.issue_reporting` switches own no rows of their own (a report belongs to its area's
repair record), and the shared technician directory is removed only by a tenant purge.
"""

from .module_purge_collectors_single_model import _counts, _delete

ITEM_SUBJECTS = {"inventory": ("inventory_product", "inventory_asset"), "rooms": ("bookable_space",)}


def _issues(space, area):
    from apps.maintenance.models import IssueReport
    return IssueReport.objects.filter(makerspace=space, area=area)


def _photos(space, area):
    from apps.maintenance.models import IssuePhoto
    return IssuePhoto.objects.filter(issue__makerspace=space, issue__area=area)


def repairs_plan(area):
    def delete(space, cursor):
        photos = _photos(space, area).count()
        issues, labels = _delete(_issues(space, area))
        return _counts(model_labels=labels, issues=issues, photos=photos)

    def preview(space):
        from apps.maintenance.models import TechnicianDispatch
        return {"issues": _issues(space, area).count(), "photos": _photos(space, area).count(),
                "dispatches": TechnicianDispatch.objects.filter(issue__makerspace=space, issue__area=area).count()}

    def keys(space, add):
        for key in _photos(space, area).values_list("object_key", flat=True):
            add(key)
            add(f"staging/{key}")

    def sizes(space):
        return dict(_photos(space, area).values_list("object_key", "size_bytes"))

    return delete, preview, keys, sizes


def maintenance_plan(area):
    subjects = ITEM_SUBJECTS[area]

    def querysets(space):
        from apps.maintenance.models import (
            RoomOutage, SubjectMaintenanceLog, SubjectMaintenanceSchedule, WorkOrder,
        )
        rows = [SubjectMaintenanceLog.objects.filter(makerspace=space, subject_type__in=subjects),
                SubjectMaintenanceSchedule.objects.filter(makerspace=space, subject_type__in=subjects),
                WorkOrder.objects.filter(makerspace=space, subject_type__in=subjects)]
        if area == "rooms":
            rows.append(RoomOutage.objects.filter(makerspace=space))
        return rows

    def delete(space, cursor):
        counts, labels = {}, frozenset()
        for queryset in querysets(space):
            count, owned = _delete(queryset)
            counts[queryset.model._meta.model_name] = count
            labels |= owned
        return _counts(model_labels=labels, **counts)

    def preview(space):
        return {queryset.model._meta.model_name: queryset.count() for queryset in querysets(space)}

    return delete, preview


def plans(plan_type):
    machines, inventory, rooms = (repairs_plan(area) for area in ("machines", "inventory", "rooms"))
    items, room_upkeep = maintenance_plan("inventory"), maintenance_plan("rooms")
    note = " Reports, history, photos, technician sends and parts; the technician directory stays."
    return (
        plan_type("machines.repairs", "Machine issues and repair jobs." + note, *machines),
        plan_type("inventory.repairs", "Item issues and repair jobs." + note, *inventory),
        plan_type("bookings.room_repairs", "Room issues and repair jobs." + note, *rooms),
        plan_type("inventory.maintenance", "Item and unit maintenance schedules, logs and work orders.", *items),
        plan_type("bookings.room_maintenance", "Room maintenance schedules, logs, work orders and outages.",
                  *room_upkeep),
    )
