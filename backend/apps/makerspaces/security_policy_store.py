"""Storage for ``policy``-backed security settings: one ``MakerspaceSecurityPolicy`` row per space.

Only ``security_settings`` writes here, inside its row lock on the space; the pre-save
guard in ``security_lock_guard`` keeps every other writer from changing a value.
"""

from .models_security import MakerspaceSecurityPolicy
from .security_lock_guard import SERVICE_WRITE_ATTR


def policy_values(space):
    """The space's stored values, or ``{}`` when it has never set one."""
    if getattr(space, "pk", None) is None:
        return {}
    row = MakerspaceSecurityPolicy.objects.filter(makerspace_id=space.pk).values_list("values", flat=True).first()
    return dict(row or {})


def write(space, key, value):
    """Persist one normalized value through the guarded save (caller holds the space lock)."""
    row = MakerspaceSecurityPolicy.objects.select_for_update().filter(makerspace_id=space.pk).first()
    if row is None:
        row = MakerspaceSecurityPolicy(makerspace_id=space.pk, values={})
    row.values = {**(row.values or {}), key: value}
    setattr(row, SERVICE_WRITE_ATTR, {key: value})
    try:
        row.save()
    finally:
        delattr(row, SERVICE_WRITE_ATTR)
