"""DY-61: the Event Manager's event report switches, through the settings-authority layer.

`reports.event_pdf` and `reports.event_exports` are parented to `reports`, so no domain
manager owned them and only a Space Manager could switch them -- breaking "the Event
Manager customises events fully". They are now `events` settings in the authority
registry: the Space Manager always edits them; the Event Manager only while holding the
events settings grant (#101, #128 C-11c) and never past a Space Manager lock. Without the
grant they are read-only. Writes reuse the one makerspace settings path (`save_space`),
so capability prerequisites (events + reports installed) are validated as everywhere else.
"""

from django.db import transaction

from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from config.locale_resolution import display

MODULE = "events"
KEYS = ("reports.event_pdf", "reports.event_exports")


def describe(actor, makerspace):
    from apps.makerspaces.capabilities import FEATURES
    from apps.makerspaces.models_settings_authority import ModuleSettingLock
    from apps.makerspaces.settings_authority import decide

    locks = set(ModuleSettingLock.objects.filter(
        makerspace=makerspace, setting_key__in=KEYS, released_at__isnull=True,
    ).values_list("setting_key", flat=True))
    stored = set(makerspace.enabled_features or [])
    rows = []
    for key in KEYS:
        decision = decide(actor, makerspace, MODULE, key)
        rows.append({"key": key, "label": display(FEATURES[key].label), "description": display(FEATURES[key].description),
                     "enabled": key in stored, "effective": configuration_feature_enabled(makerspace, key),
                     "editable": decision.allowed, "locked": key in locks, "code": decision.code})
    return {"switches": rows}


def apply(actor, makerspace, changes):
    """Set each switch in `changes` ({key: bool}); refuse the whole request on any refusal."""
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.settings_authority import assert_setting_write, record_change
    from apps.makerspaces.setup_settings import save_space
    from apps.tenant_migration.gate_runtime import tenant_write

    with tenant_write(makerspace.pk), transaction.atomic():
        locked = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        stored = set(locked.enabled_features or [])
        moved = {key: bool(on) for key, on in changes.items() if (key in stored) != bool(on)}
        decisions = {key: assert_setting_write(actor, locked, MODULE, key) for key in moved}
        if not moved:
            return locked
        added = {key for key, on in moved.items() if on}
        removed = {key for key, on in moved.items() if not on}
        saved = save_space(actor, locked, {"enabled_features": sorted((stored | added) - removed)})
        for key, on in moved.items():
            record_change(actor, saved, MODULE, key, not on, on, decisions[key])
        return saved
