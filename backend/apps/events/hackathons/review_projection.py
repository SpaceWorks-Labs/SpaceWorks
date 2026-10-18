"""Blind review is enforced here, never by hiding React fields."""
import hashlib
import hmac
import json
from django.conf import settings
from apps.events import event_authority
from .admission_errors import fail

IDENTIFYING = {"date_of_birth", "email", "phone", "url", "asset_reference", "emergency_contact"}
PRIVATE_KEYS = {"name", "phone", "email", "institution", "github", "linkedin", "portfolio", "resume",
                "dietary_needs", "accessibility_needs", "emergency_contact", "date_of_birth"}


def alias(event_id, application_id):
    key = settings.SECRET_KEY.encode()
    digest = hmac.new(key, f"application:{event_id}:{application_id}".encode(), hashlib.sha256).hexdigest()[:10]
    return "Applicant " + digest.upper()


def reviewer_answers(snapshot, schema, *, blind):
    if snapshot.get("version") != 2 or not isinstance(schema, dict):
        # Legacy schemas have no reviewed disclosure contract; disclose nothing.
        return []
    questions = {q["id"]: q for q in schema.get("questions", [])}
    result = []
    for entry in snapshot.get("answers", []):
        question = questions.get(entry.get("id"))
        if not question or question.get("disclosure", {}).get("reviewer") is not True:
            continue
        if blind and (question.get("identifying") or question.get("profile_field_key") in PRIVATE_KEYS
                      or question.get("type") in IDENTIFYING):
            continue
        if "derivation_id" in entry:
            # Age/DOB never participate in admission review.
            continue
        result.append({k: entry[k] for k in ("id", "label", "type", "value") if k in entry})
    return result


def project_application(application, config):
    return {"id": application.pk, "event_id": application.event_id, "version": application.version,
            "state": application.state, "alias": alias(application.event_id, application.pk),
            "answers": reviewer_answers(json.loads(application.answers_snapshot), config.application_form, blind=config.blind_review),
            "blind": config.blind_review,
            "blind_notice": "Do not include identifying information in review answers. Free text can reveal identity." if config.blind_review else None}


def project_assignment(assignment, *, actor, config):
    event_authority.require(actor, assignment.event, "review_applications")
    if assignment.reviewer_id != actor.pk:
        fail("not_found", "Not found.", status=404)
    require_current_assignment(assignment, config=config)
    applications = list(assignment.cohort.applications.order_by("pk")) if assignment.cohort_id else [assignment.application]
    result = {"id": assignment.pk, "event_id": assignment.event_id, "version": assignment.version,
              "state": assignment.state, "round": assignment.round, "rubric": config.review_rubric,
              "allowed_actions": ["submit", "recuse"] if assignment.state == "assigned" else [],
              "applications": [project_application(a, config) for a in applications]}
    if config.review_round_closed:
        from .review_models import ApplicationReviewAssignment
        selector = {"cohort_id": assignment.cohort_id} if assignment.cohort_id else {"application_id": assignment.application_id}
        result["completed_scores"] = [a.review.scores for a in ApplicationReviewAssignment.objects.filter(
            **selector, round=assignment.round, state="submitted").select_related("review")]
    return result


def require_current_assignment(assignment, *, config):
    from .review_workflow import conflicted
    subject = assignment.cohort if assignment.cohort_id else assignment.application
    source_at = subject.sealed_at if assignment.cohort_id else subject.answers_changed_at
    applications = list(subject.applications.all()) if assignment.cohort_id else [subject]
    if (assignment.state == "recused" or source_at is None or assignment.assigned_at < source_at
            or assignment.rubric_revision != config.review_rubric.get("revision", 1)
            or any(a.state == "draft" for a in applications)
            or conflicted(assignment.event_id, assignment.reviewer_id, subject)):
        fail("not_found", "Not found.", status=404)
    return assignment


def project_review_result(assignment, *, actor, config):
    """A recusal acknowledgement never reopens the revoked answer projection."""
    if assignment.state != "recused":
        return project_assignment(assignment, actor=actor, config=config)
    event_authority.require(actor, assignment.event, "review_applications")
    if assignment.reviewer_id != actor.pk:
        fail("not_found", "Not found.", status=404)
    return {"id": assignment.pk, "event_id": assignment.event_id, "version": assignment.version,
            "state": "recused", "round": assignment.round, "rubric": config.review_rubric,
            "allowed_actions": [], "applications": []}
