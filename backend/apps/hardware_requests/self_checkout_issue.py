"""Self-checkout issue workflow and active-QR guard."""

from apps.accounts.account_kind_guards import require_member_account

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.accounts.account_obligations import lock_obligation_owner
from apps.inventory import availability
from apps.boxes.models import QrScanEvent
from apps.evidence.finalization import charge_storage_once
from apps.evidence.consumption import mark_consumed
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.direct_loan_returns import validate_evidence_upload
from apps.hardware_requests.models import PublicToolLoan
from apps.hardware_requests.self_checkout_evidence import _lock_unused_evidence, _public_evidence
from apps.hardware_requests.self_checkout_helpers import _checkout_target, _issued_request, _locked_qr
from apps.hardware_requests.workflow_errors import InvalidTransition, RequestValidationError
from apps.makerspaces.guards import require_feature, require_feature_locked
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable
from apps.makerspaces.loan_policy import loan_days
from apps.hardware_requests import kit_checklists as kits


def checkout_tool(makerspace, requester, payload, *, evidence_id, remark="", kit_checklist=None, contact=None):
    """Issue a QR tool to ``requester``; ``contact`` is an account-less borrower (#91).

    With ``contact``, ``requester`` is the space's inert principal and the confirmed
    name, phone and email form the snapshot; its key scopes the borrow limits.
    """
    # Gate on the feature and on servability BEFORE touching evidence. Promotion moved
    # out of the transaction so its row locks never span S3 I/O, and moving the evidence
    # work up with it put it ahead of the feature check -- so a makerspace with
    # self-checkout disabled reported an evidence error instead of the feature error, and
    # promoted an upload on the way there. The locked recheck below is still the
    # authority; this is the cheap pre-check that keeps the ordering honest.
    # By pk, not by the instance the caller handed us: require_feature() trusts a
    # Makerspace argument as-is, so a stale in-memory copy would pass a gate the stored
    # row has already closed.
    require_member_account(requester)
    current = require_feature(makerspace.pk, "inventory.self_checkout")
    if not is_servable(current):
        raise RequestValidationError("Makerspace is not available.")
    evidence = _public_evidence(
        makerspace, requester, evidence_id, EvidencePhoto.EvidenceType.ISSUE
    )
    finalized = validate_evidence_upload(evidence, label="Issue")
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(makerspace.pk)
        makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        makerspace = require_feature_locked(makerspace, "inventory.self_checkout")
        requester = lock_obligation_owner(requester)
        if not is_servable(makerspace):
            raise RequestValidationError("Makerspace is not available.")
        _lock_unused_evidence(evidence, issue=True)
        charge_storage_once(evidence, finalized.size)
        mark_consumed(evidence)
        qr = _locked_qr(makerspace, payload)
        if qr_has_active_loan(makerspace, qr):
            raise InvalidTransition("This QR code is already checked out.")

        target_label, product_quantities, asset_ids, container = _checkout_target(qr)
        availability.enforce_product_borrow_limits(
            makerspace, requester, product_quantities, contact_key=contact.key if contact else "",
        )
        due_at = timezone.now() + timedelta(days=loan_days(makerspace, product_quantities))
        hardware_request = _issued_request(
            makerspace,
            requester,
            "" if contact else requester.username,
            product_quantities,
            requester_name=contact.name if contact else requester.display_name,
            contact_email=contact.email if contact else requester.email,
            contact_phone=contact.phone if contact else requester.phone,
            return_due_at=due_at,
        )
        if contact:
            hardware_request.anonymous_idempotency_key_fingerprint = contact.marker
            hardware_request.anonymous_payload_fingerprint = contact.key
        hardware_request.issue_evidence = evidence
        checklist = kits.record_issue(requester, hardware_request, container, kit_checklist)
        hardware_request.issue_remark = kits.checklist_remark(str(remark or "").strip(), checklist)
        hardware_request.save(update_fields=[
            "issue_evidence", "issue_remark", "anonymous_idempotency_key_fingerprint",
            "anonymous_payload_fingerprint", "updated_at",
        ])
        loan = PublicToolLoan.objects.create(
            makerspace=makerspace,
            qr_code=qr,
            qr_ids=[qr.id],
            container=container,
            request=hardware_request,
            requester=requester,
            target_type=qr.target_type,
            target_id=qr.target_id,
            target_label=target_label,
            asset_ids=asset_ids,
            due_at=due_at,
        )
        QrScanEvent.objects.create(
            makerspace=makerspace,
            qr_code=qr,
            actor=requester,
            context=QrScanEvent.Context.ISSUE,
            request=hardware_request,
        )
        audit.record(
            None if contact else requester,
            "public_tool.checked_out",
            makerspace=makerspace,
            target=hardware_request,
            meta={"qr_id": qr.id, "target": target_label},
        )
        # Lane L15 (A10): self-checkout loans are charged like reviewed loans. An
        # account-less borrower (#91) has no account to owe it; the raise is skipped.
        if contact is None:
            from apps.hardware_requests import loan_payments
            request_id = hardware_request.pk
            transaction.on_commit(lambda: loan_payments.on_request_issued(request_id, requester))
        return loan


def qr_has_active_loan(makerspace, qr):
    """True if this QR is part of any currently checked-out loan.

    A direct handout can bundle several QRs onto one loan; only the first lands in
    the `qr_code` FK (the partial-unique constraint allows just one), so the rest
    are tracked in `qr_ids`. Checking both closes the re-issue gap where a
    secondary QR looked free. Callers hold the relevant QR row lock(s), so the
    check is race-free against concurrent checkouts of the same QR."""
    return (
        PublicToolLoan.objects.filter(
            makerspace=makerspace,
            status=PublicToolLoan.Status.CHECKED_OUT,
        )
        .filter(Q(qr_code=qr) | Q(qr_ids__contains=[qr.id]))
        .exists()
    )
