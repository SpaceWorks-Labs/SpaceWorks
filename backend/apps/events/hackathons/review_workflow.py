"""Assignment, submission and recusal have exactly one writer."""
from collections import Counter
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.accounts.models import User
from apps.events import event_authority
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .admission_ports import ports
from .admission_transactions import command, record
from .review_models import ApplicationReview, ApplicationReviewAssignment, ApplicationReviewConflict
from .team_models import HackathonTeamMember


def applications_for(subject):
    return list(subject.applications.all()) if isinstance(subject, HackathonApplicationCohort) else [subject]


def conflicted(event_id, reviewer_id, subject):
    applications = applications_for(subject)
    owners = {a.member_id for a in applications}
    if reviewer_id in owners:
        return True
    team_ids = HackathonTeamMember.objects.filter(event_id=event_id, member_id__in=owners, state="active").values("team_id")
    if HackathonTeamMember.objects.filter(event_id=event_id, member_id=reviewer_id, team_id__in=team_ids, state="active").exists():
        return True
    selector = {"cohort_id": subject.pk} if isinstance(subject, HackathonApplicationCohort) else {"application_id": subject.pk}
    return ApplicationReviewConflict.objects.filter(event_id=event_id, reviewer_id=reviewer_id, **selector).exists() or ports().subject_conflict(
        event_id=event_id, reviewer_id=reviewer_id, application_ids=tuple(a.pk for a in applications))


def validate_scores(rubric, scores):
    criteria = rubric.get("criteria", [])
    keys = {criterion["key"] for criterion in criteria}
    if not keys or set(scores) != keys or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
        fail("invalid_scores", "Score every rubric criterion from 1 to 5.", status=400)
    return scores


def assign_locked(ctx, subjects, reviewers):
    loads = Counter(ApplicationReviewAssignment.objects.filter(event=ctx.event,
        state__in=("assigned", "submitted")).values_list("reviewer_id", flat=True))
    unsatisfied = []
    for subject in subjects:
        selector = {"cohort": subject} if isinstance(subject, HackathonApplicationCohort) else {"application": subject}
        all_rounds = ApplicationReviewAssignment.objects.filter(**selector)
        source_at = subject.sealed_at if isinstance(subject, HackathonApplicationCohort) else subject.answers_changed_at
        current = all_rounds.filter(assigned_at__gte=source_at, rubric_revision=ctx.config.review_rubric.get("revision", 1))
        round_number = current.aggregate(value=Max("round"))["value"]
        if round_number is None:
            round_number = (all_rounds.aggregate(value=Max("round"))["value"] or 0) + 1
        used = set(current.values_list("reviewer_id", flat=True))
        count = current.exclude(state="recused").count()
        while count < ctx.config.review_count:
            candidates = [r for r in reviewers if r.pk not in used and not conflicted(ctx.event.pk, r.pk, subject)
                          and event_authority.can(r, ctx.event, "review_applications")]
            if not candidates:
                unsatisfied.append({"subject_id": subject.pk, "missing": ctx.config.review_count - count})
                break
            reviewer = min(candidates, key=lambda r: (loads[r.pk], r.pk))
            assignment = ApplicationReviewAssignment.objects.create(event=ctx.event, **selector,
                reviewer=reviewer, round=round_number,
                rubric_revision=ctx.config.review_rubric.get("revision", 1))
            used.add(reviewer.pk)
            loads[reviewer.pk] += 1
            count += 1
            record(ctx, "review_assigned", assignment, reviewer_id=reviewer.pk, round=assignment.round)
    return unsatisfied


def assign(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="reviews.assign", permission="review_applications") as ctx:
        if ctx.reference:
            return {"missing_coverage": ctx.reference.get("missing_coverage", [])}
        check_version(ctx.config, data["expected_version"])
        from .admission_decisions import subject_locked
        subjects = []
        seen = set()
        for item in data["subjects"]:
            if set(item) not in ({"application_id"}, {"cohort_id"}):
                fail("invalid_subject", "Choose one application or cohort ID.", status=400)
            if any(type(v) is not int or v <= 0 for v in item.values()):
                fail("invalid_subject", "Use a positive subject ID.", status=400)
            subject, applications = subject_locked(ctx.event, item)
            key = (type(subject).__name__, subject.pk)
            if key in seen or not applications or any(a.state not in ("submitted", "waitlisted") for a in applications):
                fail("invalid_subject", "Choose distinct submitted subjects.", status=400)
            seen.add(key)
            subjects.append(subject)
        reviewers = list(User.objects.filter(pk__in=data["reviewer_ids"], account_kind="member", is_active=True, access_status="active"))
        reviewers = [reviewer for reviewer in reviewers if event_authority.can(reviewer, ctx.event, "review_applications")]
        if len(reviewers) != len(set(data["reviewer_ids"])):
            fail("not_found", "Not found.", status=404)
        missing = assign_locked(ctx, subjects, reviewers)
        ctx.finish("review_assignment", ctx.config.pk, missing_coverage=missing)
        return {"missing_coverage": missing}


def submit(*, event_id, review_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"reviews.submit:{review_id}", permission="review_applications") as ctx:
        assignment = get_object_or_404(ApplicationReviewAssignment.objects.select_for_update(), pk=review_id, event=ctx.event, reviewer=actor)
        if ctx.reference:
            return assignment
        check_version(assignment, data["expected_version"])
        if assignment.state != "assigned" or ctx.config.review_round_closed:
            fail("invalid_transition", "This review is closed.")
        subject = assignment.cohort if assignment.cohort_id else assignment.application
        source_at = subject.sealed_at if assignment.cohort_id else subject.answers_changed_at
        if source_at is None or assignment.assigned_at < source_at:
            fail("review_subject_changed", "This application was resubmitted. Refresh the review assignment.")
        if "recusal_code" in data:
            assignment.state, assignment.recusal_code = "recused", data["recusal_code"]
            ApplicationReviewConflict.objects.get_or_create(event=ctx.event, reviewer=actor,
                **({"cohort": subject} if assignment.cohort_id else {"application": subject}),
                defaults={"reason_code": data["recusal_code"]})
        else:
            if conflicted(event_id, actor.pk, subject):
                fail("review_conflict", "Recuse from this application.", status=403)
            if assignment.rubric_revision != ctx.config.review_rubric.get("revision", 1):
                fail("rubric_revision_changed", "The review rubric changed.")
            scores = validate_scores(ctx.config.review_rubric, data["scores"])
            ApplicationReview.objects.create(assignment=assignment, scores=scores, notes=data.get("notes", ""))
            assignment.state, assignment.submitted_at = "submitted", timezone.now()
        assignment.version += 1
        assignment.save()
        record(ctx, "review_" + assignment.state, assignment, version=assignment.version)
        if assignment.state == "recused":
            candidates = User.objects.filter(pk__in=ports().reviewer_candidates(event_id=event_id),
                account_kind="member", is_active=True, access_status="active")
            assign_locked(ctx, [subject], list(candidates))
        ctx.finish("review", assignment.pk)
        return assignment
