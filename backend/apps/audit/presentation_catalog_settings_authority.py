"""Audit presentation for lane L17: folded capabilities and the settings-authority layer.

Owner decisions #97, #101 and #128 C-8/C-11. Every leaf here is safe for the space's
managers to read: setting keys and values, the authority a change was made under, grant
and lock identifiers and notes, and which capability's data a superadmin purged.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.capability_purge_started", "Capability data purge started", ("capability",)),
    P("makerspace.capability_purged", "Capability data purged", ("capability",)),
    P("makerspace.module_retired", "Retired module key folded into capabilities",
      ("module", "capabilities", "source")),
    P("settings.changed", "Setting changed", ("module", "key", "from", "to", "via", "grant_id")),
    P("settings.grant_created", "Settings grant created", ("module", "grant_id", "via")),
    P("settings.grant_revoked", "Settings grant revoked", ("module", "grant_id")),
    P("settings.lock_created", "Setting locked", ("setting_key", "lock_id", "note")),
    P("settings.lock_released", "Setting lock released", ("setting_key", "lock_id")),
)
