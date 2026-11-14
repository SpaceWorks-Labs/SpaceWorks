"""Decision 530: every document producer enters decide() before reserving mail.

The callback runs inside the short row-lock transaction; it must never perform transport.
Scheduling timestamps, routing metadata and logs are not dispatch permission.
"""
from dataclasses import dataclass
from django.db import transaction
from .models_document_email import DocumentEmailIntent
from .document_email_history import legacy_defaults, scoped

# These are the only changing edges. All absent (state, event) pairs are refused.
TRANSITIONS = {
    ("initial_pending", "reserve"): "sent",
    ("recovery_approved", "reserve"): "sent",
    ("initial_pending", "disabled"): "skipped_disabled",
    ("recovery_approved", "disabled"): "skipped_disabled",
    ("skipped_disabled", "disabled"): "skipped_disabled",
    ("initial_pending", "permanent"): "skipped_permanent",
    ("recovery_approved", "permanent"): "skipped_permanent",
    ("skipped_disabled", "permanent"): "skipped_permanent",
    ("skipped_disabled", "approve"): "recovery_approved",
}


@dataclass
class Decision:
    intent: DocumentEmailIntent
    allowed: bool = False
    value: object = None


def envelope_identity(envelope):
    return dict(makerspace_id=envelope.makerspace_id, document_id=int(envelope.source_id),
                recipient_id=envelope.recipient_id, intent_key=envelope.dedup_key)


def document_identity(document):
    from apps.operations.notifications_p2 import identity, revision
    version = revision(document.pk, document.issued_at)
    key = identity(document.makerspace_id, "payments.document", document.pk, version, "document_issued")
    return dict(makerspace_id=document.makerspace_id, document_id=document.pk,
                recipient_id=document.payment.member_id, intent_key=f"p2:{key}:u:{document.payment.member_id}")


def live_reason(space, user):
    from .dispatch_outbox import email_skip_reason
    space.refresh_from_db()
    user.refresh_from_db()
    return email_skip_reason(space, user.email, user_id=user.pk, feature="payments",
                             stream="payments", event="document_issued")


def initialize(document):
    if document.payment.member_id:
        return decide(**document_identity(document), event="inspect", fresh=True,
                      reason=lambda: live_reason(document.makerspace, document.payment.member))


def decide(*, makerspace_id, document_id, recipient_id, intent_key, event,
           fresh=False, reason="", eligible=True, generation=None, perform=None, defer=None, owner_kind="", owner_id=None):
    """The common serialized admission, reservation, skip and completion boundary.

    Lazy get_or_create plus the unique constraint also serializes the very first
    concurrent legacy lookup. Once created, no history is consulted again.
    """
    from apps.payments.models import PaymentDocument
    from .dispatch_outbox import DISABLED_EMAIL_REASONS
    from apps.tenant_migration.gate_runtime import tenant_write
    identity = dict(makerspace_id=makerspace_id, document_id=document_id,
                    recipient_id=recipient_id, intent_key=intent_key)
    if not intent_key or len(intent_key) > 200 or not recipient_id:
        raise ValueError("Invalid document email identity")
    with tenant_write(makerspace_id), transaction.atomic():
        if not scoped(PaymentDocument, makerspace_id).filter(pk=document_id, payment__member_id=recipient_id,
                                                            payment__makerspace_id=makerspace_id).exists():
            raise ValueError("Invalid document email owner")
        rows = scoped(DocumentEmailIntent, makerspace_id)
        row = rows.filter(**identity).first()
        if row is None:
            observed = reason() if callable(reason) else reason
            row, _ = rows.get_or_create(**identity, defaults=legacy_defaults(identity, fresh=fresh, reason=observed))
        row = rows.select_for_update().get(pk=row.pk)
        result = Decision(row)
        if generation is not None and generation != row.generation:
            return result
        if event == "inspect":
            return result
        if event == "complete":
            if row.state in {"initial_pending", "recovery_approved"}:
                # A pass with no resolvable target reserved no owner. Keep its
                # existing permission usable, but postpone its next scheduling
                # pass so unresolved work cannot monopolize a bounded sweep.
                # The generation fence above also protects this scheduling write.
                if defer:
                    result.value = defer()
                return result
            # Scheduling acknowledgement grants no dispatch authority, even for legacy rows.
            if perform:
                result.value = perform()
            result.allowed = True
            return result
        if event == "attempt":
            if row.state == "sent" and (row.owner_kind, row.owner_id) == (owner_kind, owner_id):
                result.allowed, result.value = True, perform() if perform else None
            return result
        if event == "skip_log":
            if row.state in {"skipped_disabled", "skipped_permanent"} and (
                    row.email_log_id is None or row.email_log.error != row.reason):
                row.email_log = perform(row.reason)
                row.save(update_fields=["email_log"])
                result.allowed, result.value = True, row.email_log
            return result
        observed = reason() if callable(reason) else reason
        admitted = eligible() if callable(eligible) else eligible
        if event == "approve" and (observed or not admitted):
            return result  # A denied explicit emit grants and consumes nothing.
        if event == "reserve":
            if observed:
                event = "disabled" if observed in DISABLED_EMAIL_REASONS else "permanent"
            elif not admitted:
                return result
        target = TRANSITIONS.get((row.state, event))
        if target is None:
            return result
        if event == "reserve":
            result.value = perform()
            if result.value is None:
                return result  # No selected target, therefore no owner was reserved.
            row.owner_kind = owner_kind
            row.owner_id = result.value.pk
            if owner_kind == "direct":
                row.email_log = result.value
        if event == "approve":
            row.generation += 1
            row.reason = ""
            if perform:
                result.value = perform()
        elif event in {"disabled", "permanent"}:
            row.reason = observed
        row.state = target
        row.save()
        result.allowed = True
        return result
