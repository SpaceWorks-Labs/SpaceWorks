"""An override is exact evidence for training or briefing, never waiver/CoC."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from . import commands
from .errors import ProgrammeError, check_version
from .models_roles import EventRoleAssignment
from .models_shifts import EventShift
from .models_policy import EventRequirementOverride
from .serializers import CommandSerializer


class RequirementOverrideSerializer(CommandSerializer):
    shift_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    kind = serializers.ChoiceField(choices=["training", "briefing"])
    reference_id = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000)


def override(*, actor, event_id, assignment_id, payload):
    initial = get_object_or_404(EventRoleAssignment, event_id=event_id, pk=assignment_id)

    def mutate(event, locks):
        role = get_object_or_404(EventRoleAssignment.objects.select_for_update(), event=event, pk=assignment_id)
        check_version(role, payload["expected_version"])
        shift = get_object_or_404(EventShift, event=event, pk=payload["shift_id"],
            posting_id=role.posting_id) if payload.get("shift_id") else None
        requirements = shift.requirements if shift else role.posting.requirements if role.posting_id else {}
        key = {"training": "training_ids", "briefing": "briefing_ids"}.get(payload["kind"])
        if not key or payload["reference_id"] not in requirements.get(key, []) or not payload["reason"].strip():
            raise ProgrammeError("invalid_override", "Choose a required training or briefing and explain the exception.", status=400)
        return commands.new_row(EventRequirementOverride, event, assignment=role, shift=shift,
            actor=actor, kind=payload["kind"], reference_id=payload["reference_id"], reason=payload["reason"])

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="role.requirement_override", feature=None, permission="manage_volunteers" if initial.role == "volunteer" else "manage_team",
        account_ids=(initial.member_id,), mutate=mutate, status=201)
