"""The settings-authority layer: who may change which module setting (#101, #128 C-11).

Every module setting write goes through `assert_setting_write(actor, makerspace, module,
key)`, never a bare `MANAGE_MAKERSPACE` check (LANE-RULES §13). The rules, in order:

1. **The Space Manager** (`manage_makerspace`, the superadmin included per #115) edits
   every setting in the space; their locks never bind them. `via=space_manager`.
2. **Security settings** stay outside this layer (#111 Q10/Q11): only the space's Space
   Manager or the superadmin, through `security_settings`. **Finance settings** (tax,
   billing, `payments.*`, `charges.*`, `finance.*`) are Space-Manager-only and never
   delegable. Both refuse here with `setting_not_delegated`.
3. A **module manager** must hold the module's manager action (`MODULE_MANAGER_ACTIONS`);
   without it there is nothing to delegate.
4. **An SM lock** on the key blocks every delegated edit, the fixed exception included:
   `setting_locked`. Precedence: platform security lock > Space Manager > module manager.
5. **The fixed exception (C-11d):** the Inventory Manager always changes rental timing
   (loan length, renewals, `rental_timing`) without a grant. `via=fixed_exception`.
6. **A per-person grant (C-11a)** for this module lets its holder edit; a Machine Manager
   only while their machine types cover every machine here, because machine settings are
   tenant-wide. `via=module_grant` with the grant id. Otherwise `setting_not_delegated`:
   the manager sees the settings read-only.
"""

from dataclasses import dataclass

from rest_framework import status
from rest_framework.exceptions import APIException

from apps.accounts import rbac
from apps.accounts.rbac_actions import Action

from .settings_authority_registry import (
    FIXED_EXCEPTIONS,
    MODULE_MANAGER_ACTIONS,
    is_finance_setting,
)

SPACE_MANAGER, MODULE_GRANT, FIXED_EXCEPTION = "space_manager", "module_grant", "fixed_exception"
NOT_DELEGATED, LOCKED = "setting_not_delegated", "setting_locked"


class SettingWriteRefused(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = NOT_DELEGATED

    def __init__(self, code, detail, key):
        super().__init__({"detail": detail, "code": code, "key": key}, code)
        self.code = code


@dataclass(frozen=True)
class Decision:
    allowed: bool
    via: str | None = None
    grant_id: int | None = None
    code: str | None = None
    detail: str = ""
    locked: bool = False


def is_space_manager(actor, makerspace):
    return rbac.can(actor, Action.MANAGE_MAKERSPACE, makerspace.pk)


def live_grant(makerspace, module, actor):
    from .models_settings_authority import ModuleSettingsGrant

    return ModuleSettingsGrant.objects.filter(
        makerspace=makerspace, module=module, grantee=actor, revoked_at__isnull=True,
    ).first()


def live_lock(makerspace, key):
    from .models_settings_authority import ModuleSettingLock

    return ModuleSettingLock.objects.filter(
        makerspace=makerspace, setting_key=key, released_at__isnull=True,
    ).first()


def machine_scope_covers_all(actor, makerspace):
    """A type-scoped Machine Manager reaches every machine here (settings are tenant-wide)."""
    from apps.machines.models import Machine
    from apps.machines.role_scope import EXEMPT, manage_scope_for

    scope = manage_scope_for(actor, makerspace.pk)
    if scope is EXEMPT:
        return True
    type_ids, _machine_ids = scope
    return not Machine.objects.filter(makerspace=makerspace).exclude(machine_type_id__in=type_ids).exists()


def _refuse(code, detail, *, locked=False):
    return Decision(False, code=code, detail=detail, locked=locked)


_LOOKUP = object()


def decide(actor, makerspace, module, key, *, lock=_LOOKUP, grant=_LOOKUP):
    """The authority an actor holds for one setting, without raising.

    `lock`/`grant` let a caller deciding many keys pass rows it already loaded (None is
    "there is none"); by default each is read here.
    """
    from .security_settings_registry import is_security_feature

    locked_row = live_lock(makerspace, key) if lock is _LOOKUP else lock
    if is_space_manager(actor, makerspace):
        return Decision(True, SPACE_MANAGER, locked=locked_row is not None)
    if is_security_feature(key):
        return _refuse(NOT_DELEGATED, "Only this space's Space Manager changes security settings.")
    if is_finance_setting(module, key):
        return _refuse(NOT_DELEGATED, "Finance settings are changed by the Space Manager only.")
    action = MODULE_MANAGER_ACTIONS.get(module)
    if action is None or not rbac.can(actor, action, makerspace.pk):
        return _refuse(NOT_DELEGATED, "Only the Space Manager changes this setting.")
    if locked_row is not None:
        return _refuse(LOCKED, "The Space Manager has locked this setting.", locked=True)
    for exception in FIXED_EXCEPTIONS:
        if exception.module == module and key in exception.keys and rbac.can(actor, exception.action, makerspace.pk):
            return Decision(True, FIXED_EXCEPTION)
    row = live_grant(makerspace, module, actor) if grant is _LOOKUP else grant
    if row is None:
        return _refuse(NOT_DELEGATED, "The Space Manager has not given you control of these settings.")
    if module == "machines" and not machine_scope_covers_all(actor, makerspace):
        return _refuse(NOT_DELEGATED, "Machine settings apply to every machine here; your machine types "
                                      "do not cover them all.")
    return Decision(True, MODULE_GRANT, grant_id=row.pk)


def assert_setting_write(actor, makerspace, module, key):
    """Raise a typed 403 (`setting_not_delegated` / `setting_locked`) unless allowed."""
    decision = decide(actor, makerspace, module, key)
    if not decision.allowed:
        raise SettingWriteRefused(decision.code, decision.detail, key)
    return decision


def record_change(actor, makerspace, module, key, before, after, decision):
    """`settings.changed`: who changed what, from and to, and under which authority."""
    from apps.audit import services as audit

    if before == after:
        return None
    return audit.record(actor, "settings.changed", makerspace=makerspace, target=makerspace, meta={
        "module": module, "key": key, "from": before, "to": after,
        "via": decision.via, "grant_id": decision.grant_id,
    })
