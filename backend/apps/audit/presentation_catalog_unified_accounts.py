"""Audit presentation for account unification (one account per person, #63/#65).

`account.converted` is written once per former staff account by the unification
migration: the decision, which identity fields moved to an encrypted hold (field names
only, never values), and the staff role slugs the person kept in that space.
`staff_role.granted` grants built-in staff roles to an existing person (a staff-track
row); it never creates an account.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("account.converted", "Staff account converted to a personal account", ("decision", "holds", "roles_kept")),
    P("staff_role.granted", "Staff role granted", ("membership_id", "roles", "machine_type_ids")),
)
