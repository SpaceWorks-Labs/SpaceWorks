"""The only writer of per-space security settings and their platform locks.

Authority (owner decision #111 Q10/Q11): the space's OWN Space Manager or a platform
superadmin. Not delegable, never through organization grants or module-manager grants.
Precedence: platform lock > Space Manager > module manager -- a lock is a floor the
Space Manager cannot go below, and module managers cannot edit these at all.

Recent re-authentication is the caller's job (the API views and /control/ pages hold the
request); this module holds the row lock, checks authority and the floor, writes, and
records one makerspace-scoped audit row per change. No email is sent (Q11).
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.accounts.platform_authority import is_platform_superadmin
from apps.audit import services as audit

from . import security_settings_registry as registry
from .models import Makerspace
from .models_security import MakerspaceSecurityLock
from .security_lock_guard import SERVICE_WRITE_ATTR, SecuritySettingLocked
from .servability import is_servable

SPACE, PLATFORM = "space", "platform"


def editor_via(actor, space):
    """``platform`` for a superadmin, ``space`` for this space's Space Manager, else None."""
    if not is_servable(space):
        return None
    if is_platform_superadmin(actor):
        return PLATFORM
    if (getattr(actor, "account_kind", None) == "staff" and actor.staff_makerspace_id == space.pk
            and actor.is_active and actor.access_status == "active"
            and rbac.is_space_manager_identity(actor, space.pk)):
        return SPACE
    return None


def require_editor(actor, space, via=None):
    actual = editor_via(actor, space)
    if actual is None or (via is not None and via != actual):
        raise PermissionDenied("Only this space's Space Manager or a platform superadmin can change "
                               "security settings.")
    return actual


def require_platform(actor, space):
    if not is_platform_superadmin(actor) or not is_servable(space):
        raise PermissionDenied("Only a platform superadmin can lock or unlock security settings.")


def effective(space):
    """Every registered setting with its stored value and any platform lock."""
    locks = {row.key: row for row in MakerspaceSecurityLock.objects.filter(makerspace=space)}
    rows = []
    for setting in registry.REGISTRY:
        if setting.storage != registry.FEATURE:
            continue
        lock = locks.get(setting.key)
        value = registry.stored_value(space, setting.key)
        if lock is not None:
            value = setting.stricter(value, lock.floor)
        rows.append({
            "key": setting.key, "label": setting.label, "description": setting.description,
            "kind": setting.kind, "default": setting.default, "choices": list(setting.choices),
            "value": value,
            "lock": None if lock is None else {"floor": lock.floor, "note": lock.note,
                                               "locked_at": lock.locked_at},
        })
    return rows


def _write(space, key, value):
    """Persist one feature-backed value through the guarded save."""
    features = set(space.enabled_features or [])
    (features.add if value else features.discard)(key)
    from .security_lock_guard import canonical_features
    space.enabled_features = canonical_features(features)
    setattr(space, SERVICE_WRITE_ATTR, {key: value})
    try:
        space.save(update_fields=["enabled_features", "updated_at"])
    finally:
        delattr(space, SERVICE_WRITE_ATTR)


def _locked_space(space):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    return Makerspace.objects.select_for_update().get(pk=space.pk)


def _record_change(actor, space, key, before, after, via):
    audit.record(actor, "makerspace.security_setting_changed", makerspace=space, target=space,
                 meta={"key": key, "from": before, "to": after, "via": via})


@transaction.atomic
def set_setting(actor, space, key, value, via=None):
    """Change one setting; a no-op change writes nothing and records nothing."""
    setting = registry.get(key)
    value = setting.normalize(value)
    space = _locked_space(space)
    actual = require_editor(actor, space, via)
    lock = MakerspaceSecurityLock.objects.filter(makerspace=space, key=key).first()
    if lock is not None and not setting.satisfies(value, lock.floor):
        raise SecuritySettingLocked(key)
    before = registry.stored_value(space, key)
    if before == value:
        return space
    _write(space, key, value)
    _record_change(actor, space, key, before, value, actual)
    return space


@transaction.atomic
def set_settings(actor, space, values, via=None):
    """Apply several settings atomically, in registry order."""
    if not isinstance(values, dict) or not values:
        raise ValidationError("Send at least one setting.", code="invalid_security_value")
    for key in values:
        registry.get(key)
    for setting in registry.REGISTRY:
        if setting.key in values:
            space = set_setting(actor, space, setting.key, values[setting.key], via)
    return space


@transaction.atomic
def lock(actor, space, key, floor, note=""):
    """Create or change a floor; the stored value is raised to it when it is looser."""
    setting = registry.get(key)
    floor = setting.normalize_floor(floor)
    note = (note or "").strip()
    if len(note) > 200:
        raise ValidationError("Keep the note to 200 characters.", code="invalid_security_note")
    space = _locked_space(space)
    require_platform(actor, space)
    row, created = MakerspaceSecurityLock.objects.select_for_update().get_or_create(
        makerspace=space, key=key, defaults={"floor": floor, "note": note, "locked_by": actor})
    if not created:
        row.floor, row.note, row.locked_by, row.locked_at = floor, note, actor, timezone.now()
        row.save(update_fields=["floor", "note", "locked_by", "locked_at"])
    audit.record(actor, "makerspace.security_setting_locked", makerspace=space, target=space,
                 meta={"key": key, "floor": floor, "note": note})
    before = registry.stored_value(space, key)
    raised = setting.stricter(before, floor)
    if raised != before:
        _write(space, key, raised)
        _record_change(actor, space, key, before, raised, PLATFORM)
    return row


@transaction.atomic
def unlock(actor, space, key):
    """Remove a lock; the stored value is left as it is. Only a superadmin unlocks."""
    registry.get(key)
    space = _locked_space(space)
    require_platform(actor, space)
    row = MakerspaceSecurityLock.objects.select_for_update().filter(makerspace=space, key=key).first()
    if row is None:
        return False
    floor = row.floor
    row.delete()
    audit.record(actor, "makerspace.security_setting_unlocked", makerspace=space, target=space,
                 meta={"key": key, "floor": floor})
    return True
