"""Resolve a security setting to the value that applies (#128 C-2, #111 Q9).

Order of strictness, each step only able to tighten the previous one:
platform default (deployment env, ``extra["platform_setting"]``) -> the space's stored
value -> the superadmin lock floor. A ``staff_strictest`` setting is then the strictest
of that per-space value across every space where the person holds a staff role; a person
with no staff role gets the platform default (#135 Q-A4: members use platform defaults).

Pure reads; the enforcing lanes (S-A, S-B, S-C) decide what a read failure means at
their door.
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError

from . import security_settings_registry as registry
from .models_security import MakerspaceSecurityLock, MakerspaceSecurityPolicy

logger = logging.getLogger(__name__)


def platform_default(setting):
    """The deployment's value for this setting, or the row default when it has none."""
    name = setting.extra.get("platform_setting")
    if not name:
        return setting.default
    try:
        return setting.normalize(getattr(settings, name))
    except (AttributeError, ValidationError):
        logger.warning("security_platform_default_invalid", extra={"key": setting.key, "setting": name})
        return setting.default


def _resolve(setting, values, floor):
    value = setting.stricter(platform_default(setting), registry.policy_value(setting, values))
    return value if floor is None else setting.stricter(value, floor)


def _floors(setting, makerspace_ids):
    return dict(MakerspaceSecurityLock.objects.filter(
        makerspace_id__in=makerspace_ids, key=setting.key).values_list("makerspace_id", "floor"))


def space_value(space, setting):
    """The value that applies on this space's own surfaces (any ``policy`` setting)."""
    if setting.storage != registry.POLICY:
        raise ValueError(f"{setting.key} is not a policy-backed setting.")
    row = MakerspaceSecurityPolicy.objects.filter(makerspace_id=space.pk).values_list("values", flat=True).first()
    return _resolve(setting, row or {}, _floors(setting, [space.pk]).get(space.pk))


def strictest_for_staff(user, setting):
    """The strictest value across the spaces where ``user`` holds a staff role."""
    if setting.scope != registry.STAFF_STRICTEST or setting.storage != registry.POLICY:
        raise ValueError(f"{setting.key} is not resolved per person.")
    from apps.accounts.staff_identity import staff_makerspace_ids

    ids = sorted(staff_makerspace_ids(user))
    value = platform_default(setting)
    if not ids:
        return value
    policies = dict(MakerspaceSecurityPolicy.objects.filter(makerspace_id__in=ids)
                    .values_list("makerspace_id", "values"))
    floors = _floors(setting, ids)
    for makerspace_id in ids:
        value = setting.stricter(value, _resolve(setting, policies.get(makerspace_id) or {},
                                                 floors.get(makerspace_id)))
    return value
