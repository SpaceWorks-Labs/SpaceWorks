"""Limit writes shared by every caller: one space's overrides, many spaces at once, and the platform defaults.

The DRF views validate, authorize and shape responses; the lock / read / merge / storage backfill / save /
audit sequence lives here once, so the single-space editor, the bulk editor and any control-plane caller
cannot drift apart (Codex arch-1 #10). Every function runs in one transaction and writes its audit row in it.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.audit import services as audit
from apps.makerspaces.models import Makerspace

from .limit_defaults import invalidate
from .models import PlatformLimitDefault


def _changed(old, new):
    return sorted(k for k in set(old) | set(new) if old.get(k, "unset") != new.get(k, "unset"))


def _apply_overrides(actor, space, new):
    """Write ``new`` as the locked ``space``'s complete override map; audit the keys that moved."""
    from apps.makerspaces.limits_storage_backfill import backfill_if_newly_limited
    old = dict(space.resource_limit_overrides or {})
    backfill_if_newly_limited(space, old, new)  # #261: true storage figure before the first check
    space.resource_limit_overrides = new
    space.save(update_fields=["resource_limit_overrides"])
    audit.record(actor, "space_control.limits_changed", makerspace=space, target=space,
                 meta={"changed": _changed(old, new), "overrides": new})
    return space


@transaction.atomic
def replace_space_overrides(actor, makerspace_id, overrides):
    """Replace one space's override map (already validated). 404 for an unknown space."""
    space = get_object_or_404(Makerspace.objects.select_for_update(), pk=makerspace_id)
    return _apply_overrides(actor, space, overrides)


@transaction.atomic
def bulk_update_space_overrides(actor, makerspace_ids, to_set, to_clear, *, on_unknown):
    """Set ``to_set`` and drop ``to_clear`` on every listed space, all or nothing.

    ``on_unknown(pk)`` returns the exception to raise for an id that names no space; raising it rolls
    every earlier space back.
    """
    spaces = {s.pk: s for s in Makerspace.objects.select_for_update().filter(pk__in=makerspace_ids)}
    for pk in makerspace_ids:
        space = spaces.get(pk)
        if space is None:
            raise on_unknown(pk)
        new = {k: v for k, v in (space.resource_limit_overrides or {}).items() if k not in to_clear}
        new.update(to_set)
        _apply_overrides(actor, space, new)
    return list(makerspace_ids)


def set_platform_defaults(actor, changes):
    """Apply ``{key: int | None}`` (None removes the default); audit what moved; clear the cached map."""
    with transaction.atomic():
        before = dict(PlatformLimitDefault.objects.select_for_update().values_list("key", "value"))
        for key, value in changes.items():
            if value is None:
                PlatformLimitDefault.objects.filter(key=key).delete()
            else:
                PlatformLimitDefault.objects.update_or_create(key=key, defaults={"value": value, "updated_by": actor})
        after = dict(PlatformLimitDefault.objects.values_list("key", "value"))
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        if changed:
            audit.record(actor, "managed_hosting.limit_defaults_changed", makerspace=None, target=None,
                         meta={"changed": changed, "from": {k: before.get(k) for k in changed},
                               "to": {k: after.get(k) for k in changed}})
    invalidate()
    return changed
