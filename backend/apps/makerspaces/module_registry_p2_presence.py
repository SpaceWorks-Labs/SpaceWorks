from .module_registry_definitions import GROUP_MEMBERSHIP, GUARD, ModuleDefinition

MODULES = (ModuleDefinition(
    "presence", "Presence", "Time-limited member and guest check-in, with a privacy-controlled current-presence display.",
    "presence", GUARD, group=GROUP_MEMBERSHIP, frontend_workflows=("presence_checkin", "presence_display"),
),)
