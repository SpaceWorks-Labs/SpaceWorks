"""Immutable work evidence belongs to the certificate, not a cached role label."""
from apps.events.programme_locks import current_locks
from apps.events.credentials.errors import ProgrammeConflict


def snapshot(*, event_id, assignment_id):
    from apps.events.contributions.models_roles import EventRoleAssignment
    from apps.events.contributions.certificate_subjects import resolve
    role = EventRoleAssignment.objects.get(event_id=event_id, pk=assignment_id)
    proof = {"version": 1, "role_assignment_id": role.pk, "role": role.role}
    if role.role == "volunteer":
        value = resolve(event_id=event_id, assignment_id=assignment_id, locks=current_locks(event_id))
        proof.update(minutes=value.minutes, evidence=[list(item) for item in value.evidence])
    elif role.role == "mentor":
        from apps.events.mentoring.models_rounds import MentorRoundCheckin
        proof["evidence"] = list(MentorRoundCheckin.objects.filter(event_id=event_id, mentor=role,
            round__practice_run_id=None, away=False).order_by("pk").values_list("pk", flat=True))
    elif role.role == "judge":
        from apps.events.judging.models_scoring import JudgeScore, JudgeRankingBallot
        proof["scores"] = list(JudgeScore.objects.filter(event_id=event_id,
            assignment__judge_role_assignment=role, submitted_at__isnull=False).order_by("pk").values_list("pk", "version"))
        proof["ballots"] = list(JudgeRankingBallot.objects.filter(event_id=event_id,
            judge=role).order_by("pk").values_list("pk", "version"))
        proof["scores"] = [list(item) for item in proof["scores"]]
        proof["ballots"] = [list(item) for item in proof["ballots"]]
        from apps.events.judging.models_pairwise import JudgePairwiseComparison
        # Valid decisive pairwise comparisons are judging work too (skips and invalidated rows are
        # not). Only pairwise judges carry the key, so earlier judge proofs stay byte-identical.
        compared = [list(item) for item in JudgePairwiseComparison.objects.filter(event_id=event_id,
            judge=role, invalidation__isnull=True).exclude(outcome="skip").order_by("pk").values_list("pk", "version")]
        if compared:
            proof["comparisons"] = compared
    else:
        raise ProgrammeConflict("Verified work is required.", code="certificate_ineligible")
    return proof


def require_current(certificate):
    if not certificate.role_assignment_id:
        return
    stored = certificate.layout_snapshot.get("contribution_proof")
    if not stored or snapshot(event_id=certificate.event_id, assignment_id=certificate.role_assignment_id) != stored:
        raise ProgrammeConflict("Contribution evidence changed. Reissue the certificate.", code="certificate_ineligible")


def invalidate_role_locked(*, event, assignment_id, actor=None):
    """C calls in the same transaction after an evidence correction or revocation."""
    from apps.events.models_certificates import EventAttendanceCertificate
    from .locked import save_operational
    from apps.audit.services import record
    from django.utils import timezone
    for row in EventAttendanceCertificate.objects.select_for_update().filter(event=event,
            role_assignment_id=assignment_id).exclude(status="revoked").order_by("pk"):
        row.status, row.revoked_at, row.revoked_by = "revoked", timezone.now(), actor
        row.revocation_reason = "attendance_corrected"
        save_operational(row, ("status", "revoked_at", "revoked_by", "revocation_reason"))
        record(actor, "event.certificate_revoked", makerspace=event.makerspace, target=row,
            meta={"revision": row.revision, "reason": "attendance_corrected"})
