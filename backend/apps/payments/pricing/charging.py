"""Raise a priced charge: `quote()` then `create_payment(..., pricing_snapshot=...)` (lane L15).

A total of 0 raises NO `Payment` (`amount > 0` stays a database rule); a priced charge
that came to 0 is audited as `charge.free_by_pricing` with why -- a waiver made it free,
a discount took it to 0, or a failed job is free -- so "nothing was charged" is still a
record. An item with no price at all raises nothing and records nothing.
"""

from apps.audit import services as audit


def free_reason(quote):
    if quote.waiver:
        return "waived"
    if quote.discount and quote.subtotal > 0:
        return "discount"
    if not quote.lines and "failed_job_free" in quote.notes:
        return "failed_job_free"
    return "free"


def record_free(quote, *, actor, makerspace, target, subject_type, subject_id):
    audit.record(actor, "charge.free_by_pricing", makerspace=makerspace, target=target, meta={
        "subject_type": subject_type, "subject_id": subject_id, "domain": quote.domain,
        "outcome": free_reason(quote), "waiver_id": (quote.waiver or {}).get("id"),
        "discount_id": (quote.discount or {}).get("id"),
    })


def raise_priced(quote, *, makerspace, subject_type, subject_id, member, created_by, target,
                 subject_label="", due_at=None, via_makerspace=None, audit_free=True, create=None):
    """The Payment for `quote`, or None (audited) when it costs nothing.

    `create` is the caller's own `create_payment` binding, so a domain seam keeps the
    one ledger entry point it always had (and tests can still replace it there).
    """
    from apps.payments.services import create_payment
    create = create or create_payment

    if quote.total <= 0:
        # Audited when something WOULD have been charged (a priced line waived or
        # discounted to 0, a failed job made free); an unpriced item is not a record.
        if audit_free and (quote.lines or quote.notes):
            record_free(quote, actor=created_by, makerspace=makerspace, target=target,
                        subject_type=subject_type, subject_id=subject_id)
        return None
    return create(
        makerspace=makerspace, subject_type=subject_type, subject_id=subject_id, member=member,
        amount=quote.total, currency=quote.currency, created_by=created_by, via_makerspace=via_makerspace,
        subject_label=subject_label, due_at=due_at, pricing_snapshot=quote.to_snapshot(),
    )
