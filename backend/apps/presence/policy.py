"""Shared service boundary: module, identity, presets and owned projects."""
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import APIException, NotFound

from apps.accounts import rbac
from apps.accounts.claim_sessions import claim_context
from apps.makerspaces.models import MakerspaceMembership, MemberProject
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.makerspaces.validators import validate_presence_presets
from apps.separability.registry import runtime_active
from apps.separability.tombstones import app_is_tombstoned

DEFAULT_PRESETS = (60, 120, 180, 240)


class PresenceError(APIException):
    status_code = 400

    def __init__(self, code, detail, *, status_code=400):
        self.status_code = status_code
        super().__init__({"code": code, "detail": detail}, code=code)


def require_enabled(space):
    if (app_is_tombstoned("presence") or not runtime_active("presence")
            or not is_servable(space) or not module_enabled(space, "presence")):
        raise NotFound()


def require_account(account, space):
    require_enabled(space)
    if not (account and account.is_authenticated and account.pk and account.is_active
            and account.access_status == "active" and not account.is_tenant_dump_stub):
        raise PresenceError("account_inactive", "An active signed-in account is required.", status_code=403)
    membership = MakerspaceMembership.objects.filter(user=account, makerspace=space).first()
    if membership and membership.status != "active":
        raise PresenceError("membership_inactive", "This membership is not active.", status_code=403)
    context = claim_context(account)
    if context and (membership is None or context.membership_id != membership.pk):
        raise PresenceError("claim_scope", "Claim session belongs to another makerspace.", status_code=403)
    return membership


def require_staff(actor, space, *, settings=False):
    require_enabled(space)
    action = rbac.Action.MANAGE_MAKERSPACE if settings else rbac.Action.MANAGE_MEMBERS
    if not rbac.can(actor, action, space.pk):
        raise PresenceError("presence_permission_denied", "Presence permission is required here.", status_code=403)


def presets(space):
    values = space.presence_preset_minutes or list(DEFAULT_PRESETS)
    try:
        validate_presence_presets(values)
    except ModelValidationError:
        raise PresenceError("invalid_presets", "Ask a Space Manager to configure valid presence presets.")
    return values


def validate_duration(space, minutes):
    if type(minutes) is not int or minutes not in presets(space):
        raise PresenceError("invalid_preset", "Choose one of this makerspace's presence presets.")


def owned_project(account, space, project_id, status):
    if status != "working":
        if project_id is not None:
            raise PresenceError("project_not_applicable", "Choose a project only when working.")
        return None
    project = MemberProject.objects.filter(pk=project_id, profile__membership__user=account,
                                          profile__membership__makerspace=space).first()
    if project is None:
        raise PresenceError("project_required", "Working requires one of your own projects in this makerspace.")
    return project
