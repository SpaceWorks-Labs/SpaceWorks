"""Per-space archive payload formats (owner decision #144a; unified accounts, Q11).

``tenant_slice_v2`` is the raw tenant slice written since one account per person: every
membership row carries its ``track`` and the slice holds BOTH tracks, so a space's staff
roles travel and come back. ``tenant_slice_v1`` (written before) is still readable one
version back and is converted on read; anything older or unknown is refused.

A v1 archive written before the unification has no ``track`` column. Before it, a staff
account's membership held only built-in staff roles and a member's held Member alone
(M4), and the conversion migration made exactly the staff accounts' rows staff-track
(makerspaces 0114), so the primary role decides the track identically here. Staff
accounts were converted in place (same primary key), so the archive's user ids still name
the same people. A v1 archive written after the unification but before staff rows were
captured carries the track but no staff rows; the restore then blocks on the live staff
(``staff_after_restore_point``) instead of deleting them.
"""

FORMAT = "tenant_slice_v2"
PREVIOUS_FORMAT = "tenant_slice_v1"
READABLE_FORMATS = frozenset({FORMAT, PREVIOUS_FORMAT})

MEMBERSHIP = "makerspaces.MakerspaceMembership"
COMMUNITY, STAFF = "community", "staff"


def convert_rows(payload_format, label, rows, role_rows):
    """Rows of ``label`` in the current format; ``role_rows`` are the archive's roles."""
    if payload_format != PREVIOUS_FORMAT or label != MEMBERSHIP:
        return rows
    slugs = {str(row["pk"]): row["fields"].get("slug") for row in role_rows}
    converted = []
    for row in rows:
        fields = row["fields"]
        if "track" not in fields:
            slug = slugs.get(str(fields.get("assigned_role"))) or _live_slug(fields.get("assigned_role"))
            fields = {**fields, "track": STAFF if slug and slug != "member" else COMMUNITY}
        converted.append({**row, "fields": fields})
    return converted


def _live_slug(role_id):
    if role_id in (None, ""):
        return None
    from apps.makerspaces.models import MakerspaceRole

    return MakerspaceRole.objects.filter(pk=role_id).values_list("slug", flat=True).first()
