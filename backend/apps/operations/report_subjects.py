"""Typed subject adapters keep resource authority outside tenant RBAC scope."""

from django.utils.translation import gettext
from dataclasses import dataclass
from typing import Callable
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.makerspaces.guards import require_feature, require_module


@dataclass(frozen=True)
class ReportSubject:
    report_keys: tuple[str, ...]
    resolve: Callable
    authorize: Callable
    #: Tenant action of the domain's built-in manager (Event/Booking Manager). Holders
    #: pass the tenant gate below without VIEW_AUDIT; everyone else still needs it.
    tenant_action: str = ""


SUBJECTS = {}


def register(kind, adapter):
    if kind in SUBJECTS and SUBJECTS[kind] != adapter:
        raise RuntimeError(f"Duplicate report subject adapter: {kind}")
    SUBJECTS[kind] = adapter


class SubjectFilterSerializer(serializers.Serializer):
    subject_kind = serializers.CharField(max_length=48, required=False)
    subject_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if ("subject_kind" in attrs) != ("subject_id" in attrs):
            raise serializers.ValidationError(gettext("Supply subject_kind and subject_id together."))
        if attrs.get("subject_kind") and attrs["subject_kind"] not in SUBJECTS:
            raise serializers.ValidationError({"subject_kind": gettext("Unknown or unavailable subject kind.")})
        return attrs


def authorize(actor, space, definition, filters):
    serializer = SubjectFilterSerializer(data={k: v for k, v in filters.items() if k.startswith("subject_")})
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if definition.subject_kind and values.get("subject_kind") != definition.subject_kind:
        raise ValidationError({"subject_kind": gettext('This report requires {subject_kind}.').format(subject_kind=definition.subject_kind)})
    if definition.required_feature:
        require_feature(space, definition.required_feature)
    if not values:
        return None
    if space is None:
        raise PermissionDenied(gettext("Subject reports are tenant-local."))
    adapter = SUBJECTS[values["subject_kind"]]
    if definition.key not in adapter.report_keys:
        raise ValidationError({"subject_kind": gettext("Unsupported subject for this report.")})
    require_module(space, "reports")
    if not (adapter.tenant_action and rbac.can(actor, adapter.tenant_action, space.pk)):
        require_action(actor, rbac.Action.VIEW_AUDIT, space.pk)
    subject = adapter.resolve(space, values["subject_id"])
    adapter.authorize(actor, subject, definition)
    return subject


def reject_aggregate(filters):
    if any(key in filters for key in ("subject_kind", "subject_id")):
        raise ValidationError(gettext("Subject filters cannot be scheduled or aggregated."))


def subject_capable(definition):
    return any(definition.key in adapter.report_keys for adapter in SUBJECTS.values())


def report_action_allowed(actor, definition, makerspace_id, filters=None):
    """Tenant gate in front of every report run.

    Area reports are keyed to the domain manager's action. A subject-filtered run of a
    subject-capable report also admits the resource-grant path: tenant VIEW_AUDIT here,
    then the per-resource grant in `authorize` (the conjunction the parity programme introduced).
    """
    from .report_types import definition_actions
    if any(rbac.can(actor, action, makerspace_id) for action in definition_actions(definition)):
        return True
    filters = filters or {}
    subject_request = bool(definition.subject_kind) or any(
        key in filters for key in ("subject_kind", "subject_id"))
    return (subject_request and subject_capable(definition)
            and rbac.can(actor, rbac.Action.VIEW_AUDIT, makerspace_id))


def require_report_action(actor, definition, makerspace_id, filters=None):
    if not report_action_allowed(actor, definition, makerspace_id, filters):
        require_action(actor, definition.required_action, makerspace_id)
    if definition.identity_bearing:
        # A superadmin reads or exports a person-identifying report only inside an open
        # PII window on this space (owner decision #111 Q12); everyone else is unaffected.
        from apps.accounts.pii_presentation import require_pii_access
        require_pii_access(actor, makerspace_id)
