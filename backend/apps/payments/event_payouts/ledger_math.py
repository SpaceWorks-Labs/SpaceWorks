"""Payout corrections replace a chain tip; they are never extra transfers.

These pure calculations do not authorize or persist anything. The sole payout
workflow must call them under the obligation lock after all live authority checks.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .validation import METHODS, PayoutValidationError, aware, minor, reference


@dataclass(frozen=True, kw_only=True)
class Entry:
    id: UUID
    obligation_id: UUID
    chain_uuid: UUID
    currency: str
    amount_minor: int
    amends_id: UUID | None = None
    is_void: bool = False


def effective_tips(entries):
    """Refuse forks, cross-obligation links, loops and disconnected chain roots."""
    entries = tuple(entries)
    rows = {entry.id: entry for entry in entries}
    if len(rows) != len(entries):
        raise PayoutValidationError("duplicate_payout_entry")
    children, roots = {}, {}
    for entry in entries:
        if any(not isinstance(value, UUID) for value in (entry.id, entry.obligation_id, entry.chain_uuid)):
            raise PayoutValidationError("invalid_payout_identity")
        if type(entry.is_void) is not bool:
            raise PayoutValidationError("invalid_void_entry")
        minor(entry.amount_minor, zero=entry.is_void)
        if entry.is_void and (entry.amount_minor != 0 or entry.amends_id is None):
            raise PayoutValidationError("invalid_void_entry")
        if entry.amends_id is None:
            if entry.chain_uuid in roots:
                raise PayoutValidationError("duplicate_payout_chain")
            roots[entry.chain_uuid] = entry.id
            continue
        parent = rows.get(entry.amends_id)
        if (parent is None or parent.id == entry.id or parent.obligation_id != entry.obligation_id
                or parent.chain_uuid != entry.chain_uuid or parent.currency != entry.currency):
            raise PayoutValidationError("invalid_payout_amendment")
        if parent.id in children:
            raise PayoutValidationError("payout_chain_fork")
        children[parent.id] = entry.id
    reached, tips = set(), []
    for root in roots.values():
        current = root
        while True:
            if current in reached:
                raise PayoutValidationError("payout_chain_cycle")
            reached.add(current)
            if current not in children:
                tips.append(rows[current])
                break
            current = children[current]
    if len(reached) != len(entries):
        raise PayoutValidationError("payout_chain_cycle")
    return tuple(tips)


def effective_paid(entries, *, obligation_id, currency, approved_minor):
    minor(approved_minor, zero=True)
    rows = tuple(entries)
    if any(row.obligation_id != obligation_id or row.currency != currency for row in rows):
        raise PayoutValidationError("payout_scope_mismatch")
    total = sum(row.amount_minor for row in effective_tips(rows) if not row.is_void)
    if total > approved_minor:
        raise PayoutValidationError("payout_exceeds_approval")
    return total


def validate_append(entries, candidate, *, approved_minor):
    """A stale amendment cannot fork a chain, even if the total would fit."""
    rows = tuple(entries)
    if candidate.amends_id is not None and candidate.amends_id not in {row.id for row in effective_tips(rows)}:
        raise PayoutValidationError("payout_tip_changed")
    return effective_paid((*rows, candidate), obligation_id=candidate.obligation_id,
                          currency=candidate.currency, approved_minor=approved_minor)


def validate_record_metadata(*, method, payment_reference, paid_at, now):
    if not isinstance(method, str) or method not in METHODS:
        raise PayoutValidationError("invalid_payout_method")
    aware(paid_at, field="paid_at")
    aware(now, field="now")
    if paid_at > now:
        raise PayoutValidationError("payout_date_in_future")
    return {"method": method, "reference": reference(payment_reference), "paid_at": paid_at}
