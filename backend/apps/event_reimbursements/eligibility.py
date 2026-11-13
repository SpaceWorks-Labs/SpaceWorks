"""Registered canonical readers; client strings never prove country or project eligibility."""
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5
from apps.payments.event_payouts.errors import require

_facts_reader = None
_project_reader = None


def register_readers(*, facts=None, project=None):
    global _facts_reader, _project_reader
    if facts is not None:
        if _facts_reader is not None and _facts_reader is not facts:
            raise ValueError("Duplicate reimbursement facts provider")
        _facts_reader = facts
    if project is not None:
        if _project_reader is not None and _project_reader is not project:
            raise ValueError("Duplicate reimbursement project provider")
        _project_reader = project


def request_facts(*, event, owner_id):
    if _facts_reader:
        value = _facts_reader(event=event, owner_id=owner_id)
        require(isinstance(value, dict) and not set(value) - {
            "country", "cohort", "origin_country", "destination_country", "region", "mode"},
            "eligibility_provider_invalid", status=503)
        return value
    from apps.events.models import HackathonApplication, EventRegistration
    application = HackathonApplication.objects.filter(event=event, member_id=owner_id).first()
    registration = EventRegistration.objects.filter(event=event, member_id=owner_id).first()
    value = {"cohort": str(application.cohort_id)} if application and application.cohort_id else {}
    country = canonical_country(event=event, application=application, registration=registration)
    if country:
        value["country"] = country
    value.update(participation_facts(event=event, application=application, registration=registration))
    return value


STANDING = ("submitted", "offered", "waitlisted", "confirmed")


def participation_facts(*, event, application, registration):
    """Lane L21a: the review stage an application stands in, and whether this is a crew place."""
    facts = {}
    if registration is not None and registration.is_crew:
        facts["crew"] = True
    if application is not None and application.state in STANDING:
        from apps.events.hackathons.admission_stages import current_stage
        stage = current_stage(application)
        facts["application_stage"] = stage.position if stage else 0
    return facts


def canonical_country(*, event, application, registration):
    import json
    from apps.events.models import EventFormRevision
    from apps.forms_schema.profile_fields import normalize_profile_value, ProfileValueError
    snapshot = json.loads(application.answers_snapshot) if application else registration.custom_answers if registration else None
    if not isinstance(snapshot, dict) or snapshot.get("version") != 2:
        return None
    revision = EventFormRevision.objects.filter(event=event, form_key="application" if application else "registration",
        selector_kind="none", revision=snapshot.get("form_revision"), schema__form_id=snapshot.get("form_id")).first()
    if revision is None:
        return None
    questions = {q["id"] for q in revision.schema["questions"] if q.get("profile_field_key") == "country"}
    values = [row.get("value") for row in snapshot.get("answers", []) if row.get("id") in questions]
    try:
        countries = {normalize_profile_value("country", value.get("option_id") if isinstance(value, dict) else value) for value in values}
    except ProfileValueError:
        return None
    return next(iter(countries)) if len(countries) == 1 else None


def validate_request(programme, value, facts, *, defer_missing=False):
    if facts.get("staff") is True:
        # Parity C17: a staff claim (behind `events.staff_claims`) is vetted by the staff who file it, so the
        # participant country, cohort and distance rules do not apply; categories and currency still do.
        from apps.makerspaces.platform import feature_enabled
        require(feature_enabled(programme.event.makerspace, "events.staff_claims"), "staff_claims_disabled", status=403)
        return validate_categories(programme, value)
    if facts.get("crew") is True:
        # Crew expense claims (lane L21a) need their own switch; participant rules do not apply.
        from apps.makerspaces.platform import feature_enabled
        require(feature_enabled(programme.event.makerspace, "events.crew_claims"), "crew_claims_disabled", status=403)
        return validate_categories(programme, value)
    if programme.min_application_stage and not (defer_missing and "application_stage" not in facts):
        require(facts.get("application_stage", 0) >= programme.min_application_stage,
                "application_stage_required", status=400)
    if programme.eligible_countries and not (defer_missing and "country" not in facts):
        require(facts.get("country") in programme.eligible_countries, "country_ineligible", status=400)
    if programme.eligible_cohorts and not (defer_missing and "cohort" not in facts):
        require(facts.get("cohort") in programme.eligible_cohorts, "cohort_ineligible", status=400)
    if programme.min_distance_km is not None:
        from decimal import Decimal
        require(value.get("distance_km") is not None and Decimal(value["distance_km"]) >= programme.min_distance_km,
                "minimum_distance_not_met", status=400)
    validate_categories(programme, value)


def validate_categories(programme, value):
    require(all(row["category"] in programme.allowed_categories and row["category"] not in programme.exclusions
        and row["currency"] == programme.currency for row in value["estimates"]), "claim_category_ineligible", status=400)


@dataclass(frozen=True)
class ProjectEvidence:
    reference: object
    snapshot_id: int
    owner_id: int
    event_id: int


def canonical_project(*, event, owner_id, rule=("any_stage", None)):
    """G11: the snapshot that satisfies the programme's ``required_submission`` rule for this member."""
    from apps.events.submissions.stage_evidence import submission_evidence
    snapshot_id = submission_evidence(event=event, owner_id=owner_id, mode=rule[0], position=rule[1])
    if snapshot_id is None:
        return None
    return ProjectEvidence(uuid5(NAMESPACE_URL, f"spaceworks:submission-snapshot:{event.pk}:{snapshot_id}"),
                           snapshot_id, owner_id, event.pk)


def project_evidence(*, claim, programme):
    from .accepted_policy import project_required, project_rule
    if not project_required(claim.award, programme):
        return None
    require(_project_reader is not None, "project_evidence_provider_required", status=503)
    value = _project_reader(event=claim.event, owner_id=claim.member_id, rule=project_rule(claim.award, programme))
    from uuid import UUID
    require(isinstance(value, ProjectEvidence) and isinstance(value.reference, UUID) and type(value.snapshot_id) is int
            and value.snapshot_id > 0 and (value.event_id, value.owner_id) == (claim.event_id, claim.member_id),
            "project_submission_required")
    return value
