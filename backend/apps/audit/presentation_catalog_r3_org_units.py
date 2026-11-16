"""Parity O-B1: member units and unit-scoped staff. Ids, levels and counts only: never a unit's name, its payment
instructions, a member's name or an imported row's contents."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("member_unit.created", gettext_noop("Member unit created"), ("unit_id", "parent_id", "level")),
    P("member_unit.updated", gettext_noop("Member unit changed"), ("unit_id", "fields")),
    P("member_unit.moved", gettext_noop("Member unit moved"), ("unit_id", "parent_id", "descendants")),
    P("member_unit.archived", gettext_noop("Member unit archived"), ("unit_id",)),
    P("member_unit.restored", gettext_noop("Member unit restored"), ("unit_id",)),
    P("member_unit.levels_updated", gettext_noop("Member unit levels renamed"), ("levels",)),
    P("member_unit.import_reviewed", gettext_noop("Imported member reviewed by the unit lead"),
      ("imported_member_id", "unit_id", "decision", "invited")),
    P("membership.unit_changed", gettext_noop("Member moved to a unit"),
      ("membership_id", "from_unit_id", "to_unit_id", "source")),
    P("staff.unit_scope_changed", gettext_noop("Staff member's unit scope changed"),
      ("membership_id", "from_unit_id", "to_unit_id")),
    P("membership_plan.units_changed", gettext_noop("Plan limited to units"), ("plan_id", "unit_ids")),
)
