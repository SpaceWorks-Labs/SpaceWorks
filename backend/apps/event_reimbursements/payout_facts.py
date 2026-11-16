"""Canonical claim facts in the core payout preflight shape (``preflight.Facts``).

Reads only; callers decide the lock context. The evidence block is the closed G1
eligibility shape, stamped with the core eligibility revision it will become.
"""
from apps.payments.event_payouts.preflight import Facts


def facts_for(*, claim, programme, obligation):
    from .payout_preflight import current_evidence
    value = current_evidence(claim=claim, programme=programme)
    project_ok = not programme.require_project_submission or bool(value.get("project_snapshot_ref"))
    evidence = {"registration_id": value["registration_id"], "attendance_revision": value["attendance_revision"],
        "checkin_event_id": value["checkin_ids"][-1] if value["checkin_ids"] else None,
        "correction_watermark": value["invalidated_through_checkin_id"], "attestation_uuid": value["attestation_uuid"],
        "project_snapshot_ref": value.get("project_snapshot_ref"),
        "core_eligibility_revision": obligation.eligibility_revision + 1}
    attendance_ok = bool(value["eligible"]) or not value.get("attendance_required", True)
    return Facts(evidence=evidence, participation_eligible=bool(value["participation_valid"]),
        attendance_eligible=attendance_ok if value["participation_valid"] else bool(value["eligible"]),
        project_eligible=project_ok, event_active=not value["event_cancelled"],
        owner_active=bool(claim.member.is_active))


class ReimbursementPayoutFacts:
    """Installed into ``payments.event_payouts.preflight``; resolves the source claim read-only."""

    @staticmethod
    def read(*, obligation):
        from .claim_models import ReimbursementClaim
        from .config_models import ReimbursementProgramme
        claim = ReimbursementClaim.objects.select_related("award__request", "event", "member").get(
            uuid=obligation.source_uuid, event__makerspace_id=obligation.makerspace_id)
        programme = ReimbursementProgramme.objects.get(event=claim.event)
        return facts_for(claim=claim, programme=programme, obligation=obligation)
