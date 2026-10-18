"""Domain-to-core object capture selects bindings; core owns byte retention policy."""
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from .claim_models import ReimbursementClaim


def attachments(makerspace_id):
    claims = ReimbursementClaim.objects.filter(event__makerspace_id=makerspace_id).values("uuid")
    return FinanceAttachment.objects.filter(makerspace_id=makerspace_id, binding_kind="claim",
        binding_uuid__in=claims).order_by("pk")


def capture(makerspace_id, *, fidelity, now, custodial=False):
    if fidelity not in ("full", "redacted") or (fidelity == "full" and not custodial):
        raise ValueError("finance_custody_required")
    if fidelity == "redacted":
        return ()
    from apps.payments.event_payouts.object_capture import capture_attachment
    # A returned descriptor contains locators/version IDs, not plaintext PII or
    # a signed URL. The backup/import engine does I/O after closing row locks.
    return tuple(capture_attachment(row, now=now) for row in attachments(makerspace_id).iterator())


def module_private_keys(makerspace):
    """All receipt bytes are core evidence, including rejected no-liability claims."""
    return ()


def module_private_key_sizes(makerspace):
    return {}
