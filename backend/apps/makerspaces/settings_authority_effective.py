"""What the caller may edit, per module and key -- the read side of the authority layer.

One pass per module with the live grant and locks loaded once, so the console can render
lock icons and a read-only state without a request per setting. A module appears only
when the caller is the Space Manager or holds that module's manager action: the layer
never reveals another area's settings to someone who cannot see that area.
"""

from apps.accounts import rbac

from .models_settings_authority import ModuleSettingLock
from .settings_authority import decide, is_space_manager, live_grant
from .settings_authority_registry import MODULE_MANAGER_ACTIONS, setting_keys


def visible_modules(actor, makerspace):
    if is_space_manager(actor, makerspace):
        return list(MODULE_MANAGER_ACTIONS)
    return [module for module, action in MODULE_MANAGER_ACTIONS.items()
            if rbac.can(actor, action, makerspace.pk)]


def effective(actor, makerspace):
    locks = {row.setting_key: row for row in ModuleSettingLock.objects.filter(
        makerspace=makerspace, released_at__isnull=True)}
    manager = is_space_manager(actor, makerspace)
    modules = []
    for module in visible_modules(actor, makerspace):
        grant = None if manager else live_grant(makerspace, module, actor)
        keys = []
        for key in setting_keys(module):
            decision = decide(actor, makerspace, module, key, lock=locks.get(key), grant=grant)
            keys.append({
                "key": key, "editable": decision.allowed, "via": decision.via,
                "locked": key in locks, "code": decision.code,
                "lock_note": locks[key].note if key in locks else "",
            })
        modules.append({
            "module": module, "space_manager": manager,
            "grant_id": grant.pk if grant is not None else None, "keys": keys,
        })
    return {"modules": modules}
