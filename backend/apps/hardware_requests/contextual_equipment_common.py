"""Symbols shared by the contextual equipment service and its execution module.

Kept apart so neither module needs a partially-initialised import of the other.
"""
from django.http import Http404

from apps.accounts.loan_context_identity import borrower_aliases
from apps.accounts.models import User


class ProposalConflict(Exception):
    pass


def _aliases(user):
    try:
        return borrower_aliases(user)
    except (ValueError, RuntimeError, User.DoesNotExist):
        raise Http404 from None


def _require_same_outcome(receipt, proposed_kind):
    """Call only after old/new source and borrower authorization."""
    if receipt.outcome_kind != proposed_kind:
        raise ProposalConflict("operation_conflict")
