"""Programme rows for the scoped-PII leak sweep.

Most programme history is append-only (DB history guards), so every encrypted programme
field is written at INSERT, with a real parent graph that satisfies the scope, identity
and leader guards. Document fields carry the sentinel inside a JSON object.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event, EventRegistration
from apps.makerspaces.models import Makerspace

DOCUMENTS = {
    ("events.EventRegistration", "custom_answers"),
    ("events.HackathonSubmission", "form_answers"),
    ("events.SubmissionSnapshot", "project"),
}


def model(label):
    return apps.get_model(label)


def member(prefix="sweep"):
    return User.objects.create_user(username=f"{prefix}-{uuid4().hex[:10]}")


def led_team(event, leader):
    """An active team holds its leader as an active member (deferred leader guard)."""
    name = f"Sweep {uuid4().hex[:8]}"
    with transaction.atomic():
        application = model("events.HackathonApplication").objects.create(event=event, member=leader)
        team = model("events.HackathonTeam").objects.create(event=event, leader=leader, name=name,
                                                            normalized_name=name.casefold())
        model("events.HackathonTeamMember").objects.create(event=event, team=team, member=leader,
            application=application, creator=leader, state="active")
    return team, application


def role(w, kind, **values):
    return model("events.EventRoleAssignment").objects.create(event=w.event, makerspace=w.space,
        member=member(kind), role=kind, state="approved", **values)


def world():
    """Base programme graph; built inside the test's encryption and preparation context."""
    now = timezone.now()
    stamp = uuid4().hex[:8]
    space = Makerspace.objects.create(name="Programme sweep", slug=f"programme-sweep-{stamp}")
    event = Event.objects.create(makerspace=space, title="Programme sweep", starts_at=now - timedelta(hours=1),
                                 ends_at=now + timedelta(hours=4))
    w = SimpleNamespace(space=space, event=event, now=now, leader=member("leader"))
    w.team, w.application = led_team(event, w.leader)
    w.mentor = role(w, "mentor")
    w.volunteer = role(w, "volunteer")
    w.posting = model("events.EventRolePosting").objects.create(event=event, makerspace=space, role="volunteer",
        title="Sweep crew", opens_at=now - timedelta(days=1), closes_at=now + timedelta(hours=4))
    w.shift = model("events.EventShift").objects.create(event=event, makerspace=space, posting=w.posting,
        starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=3),
        signup_deadline=now + timedelta(minutes=30), task="Sweep setup")
    w.signup = model("events.EventShiftSignup").objects.create(event=event, makerspace=space, shift=w.shift,
        assignment=w.volunteer, member=w.volunteer.member)
    w.help_type = model("events.EventHelpType").objects.create(event=event, makerspace=space, key="pcb",
                                                               label="PCB help")
    w.help = model("events.EventHelpRequest").objects.create(event=event, makerspace=space, team=w.team,
        type=w.help_type, origin="team", summary="Base", exclusive_until=now + timedelta(minutes=5))
    w.round = model("events.MentorRound").objects.create(event=event, makerspace=space, index=1, key="r1",
        label="Round one", opens_at=now - timedelta(minutes=5), closes_at=now + timedelta(hours=1))
    # Project documents encrypt only under prepared tenant keys (strict programme rows).
    from apps.events.submissions.pii import prepare_documents
    with prepare_documents(event.pk):
        w.submission = model("events.HackathonSubmission").objects.create(event=event, team=w.team)
        w.snapshot = model("events.SubmissionSnapshot").objects.create(submission=w.submission, sequence=1,
            submitted_by=w.leader, project={}, content_sha256="a" * 64)
    return w


def create(label, field, value, w):
    """Insert one row of ``label`` whose mapped ``field`` holds ``value``."""
    e, s, now = w.event, w.space, w.now
    bound = {"event": e, "makerspace": s}
    if label == "events.EventRegistration":
        return EventRegistration.objects.create(event=e, name="Sweep", email=f"sweep-{uuid4().hex[:8]}@example.test",
                                                phone="1", **{field: value})
    if label == "events.HackathonApplication":
        return model(label).objects.create(event=e, member=member("applicant"), **{field: value})
    if label == "events.HackathonApplicationAnswerRevision":
        values = {"answers_snapshot": "{}", "profile_snapshot": "{}", field: value}
        return model(label).objects.create(application=w.application, sequence=1, form_schema_version=2,
                                           form_revision=1, locked_at=now, **values)
    if label == "events.ApplicationReview":
        assignment = model("events.ApplicationReviewAssignment").objects.create(event=e, application=w.application,
                                                                                reviewer=member("reviewer"))
        return model(label).objects.create(assignment=assignment, **{field: value})
    if label == "events.TeamComment":
        return model(label).objects.create(team=w.team, author=w.leader, **{field: value})
    if label == "events.EventRoleAssignment":
        return model(label).objects.create(**bound, member=member("contributor"), role="volunteer", state="draft",
                                           **{field: value})
    if label == "events.EventContributionHoursEntry":
        hours = model("events.EventContributionHours").objects.create(**bound, signup=w.signup)
        return model(label).objects.create(**bound, hours=hours, previous_version=0, minutes=30, kind="verified",
                                           **{field: value})
    if label == "events.EventShiftAttendanceCorrection":
        attendance = model("events.EventShiftAttendance").objects.create(**bound, signup=w.signup)
        return model(label).objects.create(**bound, attendance=attendance, kind="check_in", occurred_at=now,
                                           **{field: value})
    if label == "events.MentorProfile":
        return model(label).objects.create(**bound, assignment=role(w, "mentor"), **{field: value})
    if label == "events.EventHelpRequest":
        return model(label).objects.create(**bound, team=w.team, type=w.help_type, origin="team",
                                           exclusive_until=now + timedelta(minutes=5), **{field: value})
    if label == "events.EventHelpAction":
        return model(label).objects.create(**bound, request=w.help, kind="note", **{field: value})
    if label == "events.EventHelpComment":
        return model(label).objects.create(**bound, request=w.help, origin="team", **{field: value})
    if label == "events.MentorRoundLock":
        return model(label).objects.create(**bound, team=w.team, round=w.round, mentor=w.mentor, lease_uuid=uuid4(),
            expires_at=now + timedelta(minutes=5), heartbeat_at=now, started_at=now, **{field: value})
    if label == "events.MentorRoundCheckin":
        return model(label).objects.create(**bound, team=w.team, round=w.round, mentor=w.mentor, started_at=now,
                                           submitted_at=now, **{field: value})
    if label == "events.MentorConflict":
        return model(label).objects.create(**bound, mentor=w.mentor, team=w.team, kind="declared", **{field: value})
    if label == "events.MentorImportPreview":
        return model(label).objects.create(**bound, actor=w.leader, token=uuid4(), mapping_sha256="a" * 64,
                                           expires_at=now + timedelta(hours=1), **{field: value})
    if label == "events.OfficeHoursChange":
        return model(label).objects.create(**bound, slot=w.shift, **{field: value})
    if label == "events.EventRoleAnswerRevision":
        values = {"answers": "{}", "reason": "Base", field: value}
        return model(label).objects.create(**bound, assignment=w.volunteer, schema_version=2, **values)
    if label == "events.EventRequirementOverride":
        return model(label).objects.create(**bound, assignment=w.volunteer, kind="training", reference_id=1,
                                           **{field: value})
    if label == "events.JudgingReason":
        return model(label).objects.create(makerspace=s, event=e, **{field: value})
    if label == "events.JudgeScore":
        judging = model("events.JudgingRound").objects.create(event=e, key=f"final-{uuid4().hex[:6]}",
            mode="weighted_1_5", configuration={"criteria": [{"key": "quality"}]})
        assignment = model("events.JudgeAssignment").objects.create(event=e, round=judging,
            judge_role_assignment=role(w, "judge"), submission_snapshot=w.snapshot)
        return model(label).objects.create(event=e, makerspace=s, assignment=assignment,
            criterion_values={"quality": 4}, submitted_at=now, **{field: value})
    if label == "events.HackathonSubmission":
        team, _ = led_team(e, member("submitter"))
        return model(label).objects.create(event=e, team=team, **{field: value})
    if label == "events.SubmissionSnapshot":
        values = {"project": {}, field: value}
        return model(label).objects.create(submission=w.submission, sequence=2, submitted_by=w.leader,
                                           content_sha256="b" * 64, **values)
    if label == "events.SubmissionIntegrityFlag":
        return model(label).objects.create(snapshot=w.snapshot, rule_key="sweep", **{field: value})
    from tests.encryption import leak_sweep_release2
    return leak_sweep_release2.create_event(label, field, value, w)
