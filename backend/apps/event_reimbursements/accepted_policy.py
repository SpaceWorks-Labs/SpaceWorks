"""A later programme PATCH cannot silently rewrite accepted participation terms."""
from datetime import datetime


def claim_due(award, programme):
    value = award.calculation_snapshot.get("claim_due_at")
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else programme.claim_due_at


def project_required(award, programme):
    return award.calculation_snapshot.get("require_project_submission", programme.require_project_submission)


def project_rule(award, programme):
    """G11: (mode, stage position) accepted with the award; an older award's yes/no means any stage."""
    snapshot = award.calculation_snapshot
    if "required_submission" in snapshot:
        return snapshot["required_submission"], snapshot.get("required_submission_stage")
    if "require_project_submission" in snapshot:
        return ("any_stage" if snapshot["require_project_submission"] else "none"), None
    return programme.required_submission, programme.required_submission_stage


def attendance_required(award, programme):
    return award.calculation_snapshot.get("attendance_required", programme.attendance_required)
