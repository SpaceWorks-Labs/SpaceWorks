"""Exceptional finance commands and owner withdrawal share canonical parents."""
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from apps.payments.event_payouts.receipt_models import ReceiptUse, ReceiptAllocationOverride, ReceiptAllocation
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from .claim_models import ReimbursementClaim
from .claim_decision_models import ClaimAttendanceAttestation
from .budget_models import BudgetReservation
from .budget_service import release_locked
from .transactions import command, changed
from .notices import enqueue_locked


def extend(*, request, event_id, claim_id, data):
    from .claim_workflow import lock_claim_parents
    seed = ReimbursementClaim.objects.get(pk=claim_id, event_id=event_id)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"claim.extend:{claim_id}", finance=True, account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        _, _, _, claim = lock_claim_parents(ctx.event, claim_id=claim_id)
        ctx.cas(claim)
        require(claim.due_revision == data["due_revision"], "stale_due_revision")
        require(claim.state in ("draft", "open", "returned_for_info"), "claim_closed")
        previous = claim.info_due_at if claim.state == "returned_for_info" else claim.effective_due_at
        require(data["due_at"] > max(previous, timezone.now()), "invalid_deadline", status=400)
        field = "info_due_at" if claim.state == "returned_for_info" else "effective_due_at"
        changed(claim, **{field: data["due_at"]}, due_revision=claim.due_revision + 1,
                extension_reason=data.get("note", ""))
        ctx.audit("event.reimbursement.claim_extended", claim, due_revision=claim.due_revision, reason_code=data["reason_code"])
        enqueue_locked(claim, "claim_reminder")
        from .work_items import schedule_claim_locked
        schedule_claim_locked(claim)
        return ctx.finish(claim, due_revision=claim.due_revision)


def attest(*, request, event_id, claim_id, data):
    from .claim_workflow import lock_claim_parents
    from apps.events.models import EventRegistration
    seed = ReimbursementClaim.objects.get(pk=claim_id, event_id=event_id)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"claim.attest:{claim_id}", finance=True, account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        _, _, _, claim = lock_claim_parents(ctx.event, claim_id=claim_id)
        ctx.cas(claim)
        registration = EventRegistration.objects.get(pk=data["registration_id"], event=ctx.event, member_id=claim.member_id)
        require(registration.attendance_revision == data["expected_attendance_revision"], "eligibility_changed")
        require(registration.status == "attended" and ctx.event.starts_at <= data["attended_at"] <= ctx.event.ends_at,
                "invalid_attendance_attestation", status=400)
        require(bool(data["venue_evidence_refs"]), "venue_evidence_required", status=400)
        row = ClaimAttendanceAttestation.objects.create(claim=claim, registration=registration, event=ctx.event,
            owner_member_id=claim.member_id, attendance_revision=registration.attendance_revision,
            attended_at=data["attended_at"], venue_evidence_refs=data["venue_evidence_refs"],
            actor=ctx.actor, reason_code=data["reason_code"], note=data.get("note", ""), operation_id=data["operation_id"])
        changed(claim)
        ctx.audit("event.reimbursement.attendance_attested", claim, attestation_id=row.pk,
            attendance_revision=registration.attendance_revision, reason_code=data["reason_code"])
        return ctx.finish(claim, attestation_id=row.pk, attestation_uuid=str(row.uuid),
                          attendance_revision=registration.attendance_revision)


def receipt_override(*, request, event_id, claim_id, data):
    from .claim_workflow import lock_claim_parents
    seed = ReimbursementClaim.objects.get(pk=claim_id, event_id=event_id)
    ids = {item["claim_uuid"] for item in data["allocations"]}
    from .transactions import authorize
    authorize(request.user, seed.event, finance=True, request=request)
    asset_seed = FinanceAttachment.objects.filter(pk=data["asset_id"], makerspace_id=seed.event.makerspace_id,
        owner_member_id=seed.member_id, binding_kind="claim", binding_uuid=seed.uuid,
        purpose="reimbursement_receipt").values_list("generation", "sha256").first()
    owners = list(ReimbursementClaim.objects.filter(event__makerspace_id=seed.event.makerspace_id,
        uuid__in=ids).values_list("member_id", flat=True))
    event_ids = list(ReimbursementClaim.objects.filter(event__makerspace_id=seed.event.makerspace_id,
        uuid__in=ids).values_list("event_id", flat=True))
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"claim.receipt_override:{claim_id}", finance=True, account_ids=(*owners, seed.member_id),
        additional_event_ids=event_ids) as ctx:
        if ctx.replay:
            return ctx.replay
        from .config_models import ReimbursementProgramme
        from .budget_models import ReimbursementBudgetPool
        from .request_models import GrantRequest
        from .award_models import GrantAward
        list(ReimbursementProgramme.objects.select_for_update().filter(event_id__in=event_ids).order_by("pk"))
        list(ReimbursementBudgetPool.objects.select_for_update(of=("self",)).filter(programme__event_id__in=event_ids).order_by("pk"))
        list(GrantRequest.objects.select_for_update(of=("self",)).filter(award__claim__uuid__in=ids,
            event__makerspace_id=ctx.event.makerspace_id).order_by("pk"))
        list(GrantAward.objects.select_for_update(of=("self",)).filter(claim__uuid__in=ids,
            request__event__makerspace_id=ctx.event.makerspace_id).order_by("pk"))
        claims = list(ReimbursementClaim.objects.select_for_update(of=("self",)).filter(event__makerspace_id=ctx.event.makerspace_id,
            uuid__in=ids).order_by("pk"))
        claim = next((row for row in claims if row.pk == claim_id and row.event_id == event_id), None)
        require(claim is not None, "not_found", status=404)
        ctx.cas(claim)
        require({row.uuid for row in claims} == ids and claim.uuid in ids, "invalid_receipt_binding", status=404)
        require(all(row.member_id in owners for row in claims), "scope_changed")
        require(all(row.state not in ("withdrawn", "expired") for row in claims), "claim_closed")
        obligations = list(EventPayoutObligation.objects.select_for_update().filter(makerspace_id=ctx.event.makerspace_id,
            source_kind="event_reimbursement", source_uuid__in=ids).order_by("pk"))
        asset = FinanceAttachment.objects.filter(pk=data["asset_id"], makerspace_id=ctx.event.makerspace_id,
            binding_kind="claim", binding_uuid=claim.uuid, owner_member_id=claim.member_id,
            purpose="reimbursement_receipt", state__in=("ready", "attached"), scan_status__in=("clean", "skipped")).first()
        require(asset is not None and bool(asset.sha256), "receipt_unavailable", status=404)
        require(asset_seed == (asset.generation, asset.sha256), "receipt_set_changed")
        import json
        for participant in claims:
            submitted = list(participant.current_revision.lines.all()) if participant.current_revision_id else []
            draft = json.loads(participant.draft_payload).get("lines", [])
            for item in (i for i in data["allocations"] if i["claim_uuid"] == participant.uuid):
                known = any(line.line_uuid == item["line_uuid"] and line.original_amount_minor == item["original_amount_minor"]
                    and line.original_currency == data["original_currency"] and line.receipt_hash == asset.sha256 for line in submitted)
                known = known or any(str(line.get("line_uuid")) == str(item["line_uuid"]) and
                    line.get("original_amount_minor") == item["original_amount_minor"] and
                    line.get("original_currency") == data["original_currency"] and
                    line.get("receipt", {}).get("sha256") == asset.sha256 for line in draft)
                require(known, "invalid_receipt_binding", status=404)
        use, _ = ReceiptUse.objects.get_or_create(makerspace_id=ctx.event.makerspace_id, sha256=asset.sha256,
            defaults={"original_currency": data["original_currency"], "declared_total_minor": data["receipt_total_minor"]})
        use = ReceiptUse.objects.select_for_update().get(pk=use.pk)
        require(use.version == data["expected_receipt_use_version"], "stale_receipt_use_version")
        require(use.declared_total_minor == data["receipt_total_minor"] and use.original_currency == data["original_currency"],
                "receipt_total_mismatch")
        pairs = {(item["claim_uuid"], item["line_uuid"]) for item in data["allocations"]}
        require(len(pairs) == len(data["allocations"]) and sum(item["original_amount_minor"] for item in data["allocations"])
            <= use.declared_total_minor, "receipt_overallocated")
        # An override cannot silently remove an allocation in another live claim.
        existing = {(row.claim_uuid, row.line_uuid) for row in use.allocations.filter(use_version=use.version)}
        require(existing <= pairs, "receipt_allocations_incomplete")
        from apps.payments.event_payouts.queries import paid
        from apps.payments.event_payouts.eligibility_workflow import hold_for_domain_review_locked
        from uuid import uuid5
        allocations = list(use.allocations.filter(use_version=use.version))
        for obligation in obligations:
            old = {(row.line_uuid, row.amount_minor) for row in allocations if row.claim_uuid == obligation.source_uuid}
            new = {(row["line_uuid"], row["original_amount_minor"]) for row in data["allocations"]
                if row["claim_uuid"] == obligation.source_uuid}
            if old != new:
                require(paid(obligation) == 0, "claim_already_paid")
                hold_for_domain_review_locked(obligation, actor=ctx.actor,
                    operation_id=uuid5(data["operation_id"], "receipt-override:" + str(obligation.pk)),
                    reason_code="receipt_allocation_changed")
        use.version += 1
        use.save(update_fields=["version"])
        snapshot = {"allocations": [{"claim_uuid": str(i["claim_uuid"]), "line_uuid": str(i["line_uuid"]),
            "original_amount_minor": i["original_amount_minor"]} for i in data["allocations"]]}
        override = ReceiptAllocationOverride.objects.create(receipt_use=use, use_version=use.version,
            operation_id=data["operation_id"], allocation_snapshot=snapshot, total_minor=use.declared_total_minor,
            currency=use.original_currency, actor=ctx.actor, reason_code=data["reason_code"], note=data.get("note", ""))
        for item in data["allocations"]:
            ReceiptAllocation.objects.create(receipt_use=use, use_version=use.version, claim_uuid=item["claim_uuid"],
                line_uuid=item["line_uuid"], amount_minor=item["original_amount_minor"], override=override)
        changed(claim)
        ctx.audit("event.reimbursement.receipt_override", claim, override_id=str(override.pk),
                  receipt_use_id=use.pk, use_version=use.version, reason_code=data["reason_code"])
        return ctx.finish(claim, override_id=str(override.pk), receipt_use_version=use.version)


def withdraw(*, event_id, actor, data, request=None):
    from .claim_workflow import lock_claim_parents
    from .claim_finality import finalize_terminal_locked
    with command(event_id=event_id, actor=actor, request=request, data=data, action="claim.withdraw", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        _, pool, award, claim = lock_claim_parents(ctx.event, owner_id=actor.pk)
        require(claim is not None, "not_found", status=404)
        ctx.cas(claim)
        require(claim.state in ("draft", "open", "submitted", "returned_for_info"), "claim_not_withdrawable")
        require(not EventPayoutObligation.objects.filter(source_uuid=claim.uuid).exclude(state="cancelled").exists(),
                "committed_budget_requires_finance_cancellation")
        release_locked(pool, BudgetReservation.objects.select_for_update().get(award=award),
            operation_id=data["operation_id"], actor=ctx.actor, reason_code="owner_withdrawn")
        changed(award, state="closed", closed_at=timezone.now(), reason_code="owner_withdrawn")
        old = claim.state
        changed(claim, state="withdrawn")
        finalize_terminal_locked(ctx, claim, force=True)
        ctx.audit("event.reimbursement.claim_withdrawn", claim, old_state=old, new_state=claim.state)
        return ctx.finish(claim, pool_version=pool.version)
