"""Model-level backstop: security settings change only through the security service.

Every writer of ``Makerspace.enabled_features`` (the generic settings PATCH, the /control/
capability matrix, module install, space packs, setup) goes through ``Makerspace.save()``,
so one pre-save receiver covers them all. For a security key (owner decisions #111
Q9-Q11):

- a change that did not come from the security service is NOT applied: the stored value
  is put back. A change outside the service would skip the Space Manager/superadmin
  authority check, the recent re-authentication and the audit row, so no generic writer
  can change a security key at all -- and therefore none can loosen a locked one. Keeping
  the stored value (rather than failing the whole save) lets packs, setup and the
  settings PATCH keep working on everything else they carry;
- a service write that would loosen a platform-locked key below its floor is REFUSED
  with ``security_setting_locked`` (the service checks first; this is the backstop).

The service marks the instance with the exact values it intends to write. A queryset
``.update(enabled_features=...)`` would bypass this receiver; a static guard test keeps
that pattern out of the code base.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.signals import pre_save
from rest_framework import status
from rest_framework.exceptions import APIException

from . import security_settings_registry as registry

SERVICE_WRITE_ATTR = "_security_setting_writes"


class SecuritySettingLocked(APIException, DjangoValidationError):
    """A 400 on API paths and an ordinary ValidationError everywhere else."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "security_setting_locked"

    def __init__(self, key):
        label = registry.BY_KEY[key].label if key in registry.BY_KEY else key
        self.key = key
        message = f"{label} is locked by the platform and cannot be loosened."
        DjangoValidationError.__init__(self, message, code="security_setting_locked")
        APIException.__init__(self, {"detail": message, "code": "security_setting_locked", "key": key})

    def __str__(self):
        return str(self.message)


def _locked_floors(makerspace_id, keys, using):
    from .models_security import MakerspaceSecurityLock
    return dict(MakerspaceSecurityLock.objects.using(using or "default").filter(makerspace_id=makerspace_id, key__in=keys)
                .values_list("key", "floor"))


def canonical_features(features):
    """Registry order, the same as validate_capabilities; unknown legacy keys are kept."""
    from .capability_definitions import FEATURE_DEFINITIONS, FEATURES
    known = [definition.key for definition in FEATURE_DEFINITIONS if definition.key in features]
    return known + sorted(set(features) - FEATURES.keys())


def guard_security_settings(sender, instance, raw=False, update_fields=None, using=None, **kwargs):
    if raw or instance.pk is None or instance._state.adding:
        return
    if update_fields is not None and "enabled_features" not in update_fields:
        return
    stored = sender._base_manager.using(using or "default").filter(pk=instance.pk).values_list("enabled_features", flat=True).first()
    if stored is None:
        return
    before, after = set(stored or []), set(instance.enabled_features or [])
    changed = {key for key in registry.FEATURE_KEYS if (key in before) != (key in after)}
    if not changed:
        return
    intended = getattr(instance, SERVICE_WRITE_ATTR, None) or {}
    applied = {key for key in changed if intended.get(key) is (key in after)}
    floors = _locked_floors(instance.pk, applied, using) if applied else {}
    for key in sorted(applied):
        if key in floors and not registry.BY_KEY[key].satisfies(key in after, floors[key]):
            raise SecuritySettingLocked(key)
    restore = changed - applied
    if not restore:
        return
    features = set(after)
    for key in restore:
        features.discard(key)
        if key in before:
            features.add(key)
    instance.enabled_features = canonical_features(features)


def register():
    from .models import Makerspace
    pre_save.connect(guard_security_settings, sender=Makerspace,
                     dispatch_uid="makerspaces.guard_security_settings", weak=False)
