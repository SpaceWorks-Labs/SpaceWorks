"""A later programme PATCH cannot silently rewrite accepted participation terms."""
from datetime import datetime


def claim_due(award, programme):
    value = award.calculation_snapshot.get("claim_due_at")
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else programme.claim_due_at


def project_required(award, programme):
    return award.calculation_snapshot.get("require_project_submission", programme.require_project_submission)


def attendance_required(award, programme):
    return award.calculation_snapshot.get("attendance_required", programme.attendance_required)
