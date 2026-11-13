"""Deployment-global uniqueness for lane L16's rows.

An issue photo's object key is deployment-global: it is kept unless it collides on the
target, where a fresh key in the target space's prefix is generated. The room outage and
work-order slots follow their remapped rows once. Technician contact, coverage, default and
assignment constraints include a tenant-owned column, so they carry no deployment-global risk.
"""

from .unique_values_policy import PRESERVE, REMAP, _policy


def _photo_key(row, target, source_value):
    import uuid
    extension = str(source_value).rsplit(".", 1)[-1].lower()
    return f"repairs/{target.pk}/{uuid.uuid4().hex}.{extension if extension in ('jpg', 'png', 'webp') else 'jpg'}"


_FOLLOWS = "Unique per remapped room; follows the imported rows."

RULES = {
    ("maintenance.IssuePhoto", "field:object_key"): _policy(
        PRESERVE, "Keep the archived repair-photo key unless it collides on the target.", field="object_key",
        generator=_photo_key),
    ("maintenance.RoomOutage", "room_outage_one_open"): _policy(REMAP, _FOLLOWS),
    ("maintenance.IssueReport", "field:work_order"): _policy(REMAP, "One issue per work order; follows the import."),
    ("maintenance.IssueReport", "field:return_line"): _policy(
        REMAP, "One repair per damaged return line; follows the import."),
}
