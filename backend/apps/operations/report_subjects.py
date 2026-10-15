"""Typed subject adapters keep resource authority outside tenant RBAC scope."""

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
            raise serializers.ValidationError("Supply subject_kind and subject_id together.")
        if attrs.get("subject_kind") and attrs["subject_kind"] not in SUBJECTS:
            raise serializers.ValidationError({"subject_kind": "Unknown or unavailable subject kind."})
        return attrs


def authorize(actor, space, definition, filters):
    serializer = SubjectFilterSerializer(data={k: v for k, v in filters.items() if k.startswith("subject_")})
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if definition.subject_kind and values.get("subject_kind") != definition.subject_kind:
        raise ValidationError({"subject_kind": f"This report requires {definition.subject_kind}."})
    if definition.required_feature:
        require_feature(space, definition.required_feature)
    if not values:
        return None
    if space is None:
        raise PermissionDenied("Subject reports are tenant-local.")
    adapter = SUBJECTS[values["subject_kind"]]
    if definition.key not in adapter.report_keys:
        raise ValidationError({"subject_kind": "Unsupported subject for this report."})
    require_module(space, "reports")
    require_action(actor, rbac.Action.VIEW_AUDIT, space.pk)
    subject = adapter.resolve(space, values["subject_id"])
    adapter.authorize(actor, subject, definition)
    return subject


def reject_aggregate(filters):
    if any(key in filters for key in ("subject_kind", "subject_id")):
        raise ValidationError("Subject filters cannot be scheduled or aggregated.")
