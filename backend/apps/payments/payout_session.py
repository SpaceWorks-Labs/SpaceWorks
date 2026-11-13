"""Payee/payout money is session-only (decisions 219d, 224c).

An API client, a personal access token or an OAuth app connection never reads what was paid to
a person: event payouts, reimbursements, prize payouts and everything derived from them
(`payouts`, `budget_left`, `net`). One predicate and one refusal so every surface agrees.
"""
from rest_framework.exceptions import PermissionDenied
from django.utils.translation import gettext

# Report keys whose rows are payout money without a literal "payout" column.
# `receipts-payments` folds payouts into its `payments` and `closing` columns (226g).
PAYOUT_REPORT_KEYS = frozenset({"prizes-owed", "event-finance", "receipts-payments"})
# Derived from payouts: a caller without a full session loses these along with `payouts`.
PAYOUT_DERIVED_COLUMNS = ("payouts", "money_out", "net", "budget_left")


def full_session(request):
    """No API client, person credential or native device grant (decision 226g)."""
    from apps.accounts.native_session import is_native_session
    return (getattr(request, "api_client", None) is None
            and getattr(request, "person_credential", None) is None
            and not is_native_session(getattr(request, "user", None)))


def require_full_session(request):
    if not full_session(request):
        raise PermissionDenied({"detail": gettext("Payout money needs an interactive session."), "code": "full_session_required"})


def is_payout_report(definition):
    return definition.key in PAYOUT_REPORT_KEYS or any("payout" in name for name in definition.fields)


def strip_payout_columns(rows):
    return [{key: value for key, value in row.items() if key not in PAYOUT_DERIVED_COLUMNS} for row in rows]
