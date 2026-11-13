"""Atomic, field-authorized writes to the public-stat configuration."""
from django.db import transaction

from .public_stats_catalogue import WIDGETS, visibility_setting_key


def save_config(actor, makerspace, values):
    from apps.inventory.public_stats_cache import invalidate
    from apps.tenant_migration.gate_runtime import tenant_write
    from .models import Makerspace
    from .public_stats_settings import FIELDS, MODULE, _stored, read_config, setting_key
    from .settings_authority import assert_setting_write, record_change

    with tenant_write(makerspace.pk), transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        before = read_config(locked)
        # Authorize submitted keys, including no-ops, before changing any column.
        decisions = {name: assert_setting_write(actor, locked, MODULE, setting_key(name))
                     for name in FIELDS if name in values}
        visibility = values.get("visibility", {})
        widget_decisions = {key: assert_setting_write(actor, locked, WIDGETS[key].owner_module,
                                                      visibility_setting_key(key)) for key in visibility}
        changed = [name for name in decisions if values[name] != before[name]]
        changed_widgets = [key for key in visibility if visibility[key] != before["visibility"][key]]
        if not changed and not changed_widgets:
            return before
        fields = [FIELDS[name] for name in changed]
        for name in changed:
            setattr(locked, FIELDS[name], _stored(name, values[name]))
        if changed_widgets:
            raw = locked.public_stats_config
            config = dict(raw) if isinstance(raw, dict) else {}
            stored = config.get("visibility", {})
            overrides = dict(stored) if isinstance(raw, dict) and isinstance(stored, dict) else dict(before["visibility"])
            overrides.update({key: visibility[key] for key in changed_widgets})
            locked.public_stats_config = {**config, "visibility": overrides}
            fields.append("public_stats_config")
        locked.save(update_fields=[*fields, "updated_at"])
        for name in changed:
            record_change(actor, locked, MODULE, setting_key(name), before[name], values[name], decisions[name])
        for key in changed_widgets:
            record_change(actor, locked, WIDGETS[key].owner_module, visibility_setting_key(key),
                          before["visibility"][key], visibility[key], widget_decisions[key])
        transaction.on_commit(lambda: invalidate(locked.pk))
    return read_config(locked)
