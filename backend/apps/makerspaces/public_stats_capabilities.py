"""Public-stats edit hints from the same L17 decisions enforced on writes."""
from .models_settings_authority import ModuleSettingLock
from .public_stats_catalogue import WIDGETS, source_available, visibility_setting_key
from .settings_authority import decide, is_space_manager, live_grant
from .settings_authority_registry import module_for_key


def capabilities(actor, space):
    from .public_stats_settings import FIELDS, MODULE, setting_key

    locks = {row.setting_key: row for row in ModuleSettingLock.objects.filter(
        makerspace=space, released_at__isnull=True)}
    manager = is_space_manager(actor, space)
    grants = {module: None if manager else live_grant(space, module, actor)
              for module in {widget.owner_module for widget in WIDGETS.values()}}

    def field(module, key, available=True):
        decision = decide(actor, space, module, key, lock=locks.get(key), grant=grants.get(module))
        return {"editable": decision.allowed, "locked": decision.locked, "code": decision.code,
                "via": decision.via, "available": available,
                "can_lock": manager and module_for_key(key) is not None}

    return {
        "settings": {name: field(MODULE, setting_key(name)) for name in FIELDS},
        "visibility": {key: field(widget.owner_module, visibility_setting_key(key), source_available(space, key))
                       for key, widget in WIDGETS.items()},
    }
