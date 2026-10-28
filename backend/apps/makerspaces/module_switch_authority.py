"""Who may switch a module on or off (#128 C-10, superseding #77 Platform Q3).

A Space Manager enables and disables any module in their own space; switching off keeps
every row and switching back on restores it. Two things stay with the platform
superadmin:

* **installing a limit-gated module** -- on the managed platform a module whose usage is
  capped by a fair-use limit (`MANAGED_RESOURCE_LIMITS`, per-space overrides included)
  changes what the operator supports, so only the superadmin may switch it on there. On a
  self-host no limit applies (`limits.is_self_host`), so nothing is gated;
* **every purge** (`purge_module_data`, the /control/ capability purge).

The check reads the dependency closure: installing `printing` also installs
`machine_service`, so it is gated when either carries a limit.
"""

from apps.accounts import rbac

# Module key -> the managed fair-use limit keys that cap what it lets a space do.
LIMIT_GATED_MODULES = {
    "machines": ("machines",),
    "machine_service": ("machine_service_open", "machine_service_submit"),
    "printing": ("print",),
    "events": ("events",),
    "bookings": ("bookings",),
    "membership": ("members",),
    "email": ("email",),
    "telegram": ("telegram",),
    "slack": ("slack",),
    "mattermost": ("mattermost",),
    "discord": ("discord",),
    "webhook": ("webhook",),
    "sms": ("sms",),
    "whatsapp": ("whatsapp",),
    "mobile": ("native_push",),
}


def limit_gated(makerspace, key):
    """The limit keys that make installing `key` (with its requirements) superadmin-only here."""
    from apps.makerspaces import limits
    from apps.makerspaces.module_registry import with_dependencies

    if limits.is_self_host():
        return []
    installed = set(makerspace.enabled_modules or [])
    return sorted({
        limit_key
        for module in with_dependencies({key}) - installed
        for limit_key in LIMIT_GATED_MODULES.get(module, ())
        if limits.resource_limit(makerspace, limit_key) is not None
    })


def may_install(actor, makerspace, key):
    from apps.accounts.platform_authority import is_platform_superadmin

    if is_platform_superadmin(actor):
        return True
    return rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk) and not limit_gated(makerspace, key)


def may_uninstall(actor, makerspace):
    return rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace.pk)
