"""Grant and lock writes for the settings-authority layer, Space Manager only and audited.

A grant names one person (C-11a) who holds the module's manager action here and is not
already a Space Manager (who needs none). A lock names one known setting key; security
keys are locked by the platform in `security_settings`, never here. Rows are append-only:
revoking or releasing ends the live row, and the next grant or lock is a new row.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from .models_settings_authority import ModuleSettingLock, ModuleSettingsGrant
from .settings_authority import is_space_manager
from .settings_authority_registry import MODULE_MANAGER_ACTIONS, module_for_key

SPACE_MANAGER, MIGRATION = "space_manager", "migration"


def _require_manager(actor, makerspace):
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    if not is_space_manager(actor, makerspace):
        raise PermissionDenied(gettext("Only the Space Manager decides who may change settings."))
    assert_write_allowed(makerspace.pk)


def _module(module):
    if module not in MODULE_MANAGER_ACTIONS:
        raise ValidationError({"module": gettext('Choose one of: {value}.').format(value=', '.join(sorted(MODULE_MANAGER_ACTIONS)))})
    return module


def eligible_grantee(makerspace, module, user):
    return (user is not None and rbac.can(user, MODULE_MANAGER_ACTIONS[module], makerspace.pk)
            and not is_space_manager(user, makerspace))


def create_grant(actor, makerspace, module, grantee, *, via=SPACE_MANAGER):
    grant = ModuleSettingsGrant.objects.create(
        makerspace=makerspace, module=module, grantee=grantee, granted_by=actor,
    )
    audit.record(actor, "settings.grant_created", makerspace=makerspace, target=grant,
                 meta={"module": module, "grant_id": grant.pk, "via": via})
    return grant


def revoke_grant(actor, grant):
    grant.revoked_at, grant.revoked_by = timezone.now(), actor
    grant.save(update_fields=["revoked_at", "revoked_by"])
    audit.record(actor, "settings.grant_revoked", makerspace=grant.makerspace, target=grant,
                 meta={"module": grant.module, "grant_id": grant.pk})
    return grant


@transaction.atomic
def set_grants(actor, makerspace, module, grantee_ids):
    """Make the live grants for one module exactly `grantee_ids`; returns the live rows."""
    from apps.accounts.models import User

    _require_manager(actor, makerspace)
    module = _module(module)
    wanted = set(grantee_ids)
    people = {user.pk: user for user in User.objects.filter(pk__in=wanted)}
    refused = sorted(pk for pk in wanted if not eligible_grantee(makerspace, module, people.get(pk)))
    if refused:
        raise ValidationError({"grantee_ids": (
            gettext("Not this space's {module} managers (or already a Space Manager): {refused}.").format(module=module, refused=refused))})
    live = {row.grantee_id: row for row in ModuleSettingsGrant.objects.select_for_update().filter(
        makerspace=makerspace, module=module, revoked_at__isnull=True)}
    for grantee_id in sorted(set(live) - wanted):
        revoke_grant(actor, live[grantee_id])
    for grantee_id in sorted(wanted - set(live)):
        create_grant(actor, makerspace, module, people[grantee_id])
    return list(ModuleSettingsGrant.objects.filter(
        makerspace=makerspace, module=module, revoked_at__isnull=True).select_related("grantee"))


@transaction.atomic
def set_lock(actor, makerspace, setting_key, locked, note=""):
    """Lock or release one setting; returns the live lock row or None."""
    from .security_settings_registry import is_security_feature

    _require_manager(actor, makerspace)
    if is_security_feature(setting_key) or module_for_key(setting_key) is None:
        raise ValidationError({"setting_key": gettext("Not a delegable module setting of this space.")})
    row = ModuleSettingLock.objects.select_for_update().filter(
        makerspace=makerspace, setting_key=setting_key, released_at__isnull=True).first()
    if locked and row is None:
        row = ModuleSettingLock.objects.create(makerspace=makerspace, setting_key=setting_key,
                                               locked_by=actor, note=str(note or "")[:200])
        audit.record(actor, "settings.lock_created", makerspace=makerspace, target=row,
                     meta={"setting_key": setting_key, "lock_id": row.pk, "note": row.note})
    elif not locked and row is not None:
        row.released_at, row.released_by = timezone.now(), actor
        row.save(update_fields=["released_at", "released_by"])
        audit.record(actor, "settings.lock_released", makerspace=makerspace, target=row,
                     meta={"setting_key": setting_key, "lock_id": row.pk})
        row = None
    return row
