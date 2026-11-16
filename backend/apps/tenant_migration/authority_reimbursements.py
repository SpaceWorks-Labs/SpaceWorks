"""Reimbursement, stage-form and payout authorization sources stay visible to the drift guard.

Their own rows do not travel yet (catalog_reimbursements); these declarations cover the
exported fields of travelling models that their authorization/eligibility code reads.
"""

SOURCE_PATHS = (
    "event_reimbursements/accepted_policy.py",
    "event_reimbursements/attendance.py",
    "event_reimbursements/claim_commands.py",
    "event_reimbursements/claim_decisions.py",
    "event_reimbursements/eligibility.py",
    "event_reimbursements/http.py",
    "event_reimbursements/lifecycle_hooks.py",
    "event_reimbursements/payout_preflight.py",
    "event_reimbursements/purge.py",
    "event_reimbursements/transactions.py",
    "events/staged_forms/guards.py",
    "events/staged_forms/http.py",
    "events/staged_forms/policy.py",
    "events/staged_forms/transactions.py",
    "events/staged_forms/trigger_service.py",
    "events/staged_forms/upload_policy.py",
    "payments/event_payouts/authority.py",
    "payments/event_payouts/http.py",
    "payments/event_payouts/preflight.py",
    "payments/event_payouts/transactions.py",
)

_VENUE = ("Venue kind decides which attendance evidence qualifies for a reimbursement claim; an imported "
          "event keeps its authored kind and the claim it gated never travels.")
FIELDS = {
    ("events.Event", "location_kind"): _VENUE,
    ("events.EventSeries", "location_kind"): _VENUE,
}
