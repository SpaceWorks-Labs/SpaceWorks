"""Gates for the capabilities folded out of the retired `maintenance`/`procurement` keys.

Owner decisions #97, #95 and #128 C-9. Each parent has its own switch, and a surface whose
switch is off answers **404** (the feature does not exist for this space), exactly as
`require_module` does since #183B. Switching off keeps every row; purging them is the
separate superadmin action in `capability_purge`.

One To-Buy list and one warranty app serve two parents, so the row decides the switch:

* a To-Buy row's `kind` is its domain -- `printing` rows are machine consumables
  (`machines.tobuy`), `hardware` rows are inventory items (`inventory.tobuy`);
* a warranty's host is its subject kind -- a machine (`machines.warranty`) or an asset
  (`inventory.warranty`).

A machines switch therefore never hides inventory rows, and the reverse.
"""

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

MACHINES_MAINTENANCE = "machines.maintenance"
MACHINES_TOBUY = "machines.tobuy"
INVENTORY_TOBUY = "inventory.tobuy"
MACHINES_WARRANTY = "machines.warranty"
INVENTORY_WARRANTY = "inventory.warranty"

# ToBuyItem.Kind value -> the parent switch that owns those rows.
TOBUY_BY_KIND = {"printing": MACHINES_TOBUY, "hardware": INVENTORY_TOBUY}
TOBUY_KEYS = (MACHINES_TOBUY, INVENTORY_TOBUY)
WARRANTY_KEYS = (MACHINES_WARRANTY, INVENTORY_WARRANTY)


def capability_on(makerspace, key):
    """Effective switch: stored, parent module installed, owning app shipped."""
    from .platform import feature_enabled

    return feature_enabled(makerspace, key)


def _makerspace(makerspace_or_id):
    from .models import Makerspace

    if isinstance(makerspace_or_id, Makerspace):
        return makerspace_or_id
    return get_object_or_404(Makerspace, pk=makerspace_or_id)


def _refuse(key):
    raise NotFound({"detail": f"{key} is switched off for this makerspace.",
                    "code": "capability_disabled"})


def require_capability(makerspace_or_id, key):
    makerspace = _makerspace(makerspace_or_id)
    if not capability_on(makerspace, key):
        _refuse(key)
    return makerspace


def require_any_capability(makerspace_or_id, keys):
    makerspace = _makerspace(makerspace_or_id)
    if not any(capability_on(makerspace, key) for key in keys):
        _refuse(" / ".join(keys))
    return makerspace


def require_capability_locked(makerspace_or_id, key):
    """Re-check under the makerspace row lock, as `require_module_locked` does (plan A8).

    A capability toggle writes the same row, so NO KEY UPDATE serializes a creator against
    a concurrent switch-off without conflicting with deferred FK checks at commit.
    """
    from .models import Makerspace

    pk = makerspace_or_id.pk if isinstance(makerspace_or_id, Makerspace) else makerspace_or_id
    locked = Makerspace.objects.select_for_update(no_key=True).get(pk=pk)
    if not capability_on(locked, key):
        _refuse(key)
    return locked


def tobuy_key(kind):
    return TOBUY_BY_KIND[kind]


def tobuy_kinds_on(makerspace):
    """To-Buy row kinds whose parent switch is on here, in a stable order."""
    return [kind for kind, key in TOBUY_BY_KIND.items() if capability_on(makerspace, key)]


def warranty_key_for(warranty):
    return MACHINES_WARRANTY if warranty.machine_id else INVENTORY_WARRANTY
