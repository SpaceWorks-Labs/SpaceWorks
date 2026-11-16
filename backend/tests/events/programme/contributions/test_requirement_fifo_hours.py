from types import SimpleNamespace
from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.audit.models import AuditLog
from apps.events.models import EventStaffGrant
from apps.events.contributions import shift_workflow, attendance_workflow, requirements_workflow
from apps.events.contributions.models import (EventShiftSignup, EventShiftAttendance, EventContributionHours, EventContributionHoursEntry)
from apps.events.contributions.errors import ProgrammeError
from tests.events.programme.contributions.completion_helpers import role_setup, command


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("requirement_lost", [False, True])
def test_withdrawal_promotes_fifo_using_fenced_issuer_and_skips_lost_requirements(settings, requirement_lost):
    space, event, posting, shift, users, roles, adapter, manager = role_setup(settings)
    posting.permission_preset = shift.permission_preset = ["check_in"]
    posting.save(update_fields=["permission_preset"])
    shift.save(update_fields=["permission_preset"])
    def ensure(**kwargs):
        assert kwargs["member_id"] in kwargs["locks"].account_ids
        assert manager.pk in kwargs["locks"].account_ids
        row, _ = EventStaffGrant.objects.get_or_create(event=event, makerspace=space,
            user_id=kwargs["member_id"], defaults={"granted_by": manager, "permissions": []})
        return row.pk
    adapter.grants = SimpleNamespace(ensure_container_locked=ensure, write_display_union_locked=lambda **kwargs: None)
    rows = [shift_workflow.apply(actor=user, event_id=event.pk, shift_id=shift.pk,
        payload=command(shift, role_assignment_id=role.pk)).row for user, role in zip(users, roles)]
    assert [row.state for row in rows] == ["approved", "waitlisted"]
    refused = {users[1].pk} if requirement_lost else set()
    def requirements(**kwargs):
        if kwargs["actor_id"] in refused:
            raise ProgrammeError("training_required", "Training was withdrawn.", status=403)
    adapter.require_requirements = requirements
    shift_workflow.transition(actor=users[0], event_id=event.pk, signup_id=rows[0].pk,
        payload=command(rows[0]), action="withdraw")
    rows[1].refresh_from_db()
    assert rows[1].state == ("waitlisted" if requirement_lost else "approved")
    if not requirement_lost:
        assert rows[1].approved_by_id == manager.pk
        return
    refused.clear()
    # Staff approval still validates real requirements after the skip.
    result = shift_workflow.transition(actor=manager, event_id=event.pk, signup_id=rows[1].pk,
        payload=command(rows[1]), action="approve")
    assert result.row.state == "approved"


@pytest.mark.django_db
def test_only_exact_training_briefing_can_be_overridden_and_waiver_remains_live(settings):
    _, event, posting, _, users, roles, adapter, manager = role_setup(settings)
    posting.requirements = {"training_ids": [51], "host_waiver_required": True}
    posting.save(update_fields=["requirements"])
    result = requirements_workflow.override(actor=manager, event_id=event.pk, assignment_id=roles[0].pk,
        payload=command(roles[0], kind="training", reference_id=51, reason="Equivalent training verified"))
    seen = []
    def refuse_waiver(**kwargs):
        seen.extend(kwargs["override_ids"])
        raise ProgrammeError("waiver_required", "Accept the real waiver.", status=403)
    adapter.require_requirements = refuse_waiver
    from apps.events.contributions.role_policy import require_requirements
    with pytest.raises(ProgrammeError):
        require_requirements(actor_id=users[0].pk, assignment_id=roles[0].pk, shift_id=None)
    assert seen == [result.row.pk]
    serializer = requirements_workflow.RequirementOverrideSerializer(data={
        "operation_id": str(uuid4()), "expected_version": 1, "kind": "waiver", "reference_id": 51, "reason": "Staff override"})
    assert not serializer.is_valid()


@pytest.mark.django_db
def test_hours_correction_keeps_previous_evidence_and_private_reason_out_of_audit(settings):
    space, event, _, shift, users, roles, _, manager = role_setup(settings)
    signup = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift, member=users[0], assignment=roles[0], state="approved")
    EventShiftAttendance.objects.create(event=event, makerspace=space, signup=signup, state="checked_out",
        checked_in_at=timezone.now() - timedelta(hours=1), checked_out_at=timezone.now())
    EventContributionHours.objects.create(event=event, makerspace=space, signup=signup, minutes=60)
    signup = attendance_workflow.command(actor=manager, event_id=event.pk, signup_id=signup.pk,
        payload=command(signup), action="verify_hours", staff=True).row
    signup = attendance_workflow.command(actor=manager, event_id=event.pk, signup_id=signup.pk,
        payload=command(signup, minutes=45, reason="Private desk correction"), action="adjust_hours", staff=True).row
    hours = EventContributionHours.objects.get(signup=signup)
    assert hours.state == "adjusted" and hours.minutes == 45
    assert list(EventContributionHoursEntry.objects.filter(hours=hours).order_by("pk").values_list("kind", flat=True)) == ["verified", "adjusted"]
    assert "Private desk correction" not in str(list(AuditLog.objects.values()))
