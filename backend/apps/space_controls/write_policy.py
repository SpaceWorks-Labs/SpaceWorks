"""The one write guard for paused (suspended) and read-only spaces (#185).

``assert_space_writable`` is called from the source gate's single state check
(``tenant_migration.gate_runtime._assert_gate_state``), which every tenant write already
passes through: the HTTP gate middleware and the late DRF guard, every service's
``tenant_write``, every Celery task bound to a tenant, every fan-out sweep and email /
notification delivery. So no view, task or message needs its own patch.

* SUSPENDED refuses every write in every context, except the permits below (money that a
  payer already sent must still settle; the superadmin's own controls; ``/control/``).
* READ-ONLY refuses only where enforcement is switched on: unsafe HTTP requests (all
  roles, the superadmin included, except exports, the space controls and ``/control/``)
  and scheduled sweeps that create records. Delivery of existing messages, expiry,
  retention and settlement keep running, because they create nothing new.
"""

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar

READ_ONLY = "read_only"
SUSPENDED = "suspended"
BOTH = frozenset({READ_ONLY, SUSPENDED})

_enforce_read_only = ContextVar("space_controls_enforce_read_only", default=False)
_permits = ContextVar("space_controls_permits", default=frozenset())

# The superadmin's own controls must work on the very space they pause.
CONTROL_ROUTES = frozenset("""
admin-space-suspend admin-space-unsuspend admin-space-read-only admin-space-read-only-lift
admin-space-schedule admin-space-schedule-cancel admin-space-archive admin-space-unarchive
admin-space-purge admin-space-transfer-ownership admin-space-plan
""".split())
# Money a payer already sent settles in every state (the archived-money invariant).
SETTLEMENT_ROUTES = frozenset("""
stripe-webhook razorpay-webhook managed-hosting-stripe-webhook managed-hosting-razorpay-webhook
""".split())
# Read-only means "view and export": producing an export file or opening a PII window
# creates no domain record. Opt-outs and provider bounce receipts only PROTECT people
# (stop mail to them), so they keep working too.
READ_ONLY_ROUTES = frozenset("""
one-click-unsubscribe email-bounce-webhook email-provider-webhook telegram-webhook
data-export-list-create data-export-detail data-export-download-url member-subject-export-list
member-subject-export-detail member-saved-details-export-create admin-makerspace-pii-access
admin-inventory-export to-buy-export report-export ledger-export finance-event-payout-export
admin-card-design-export member-admission-export events-programme-member-role-application-export
""".split())

SETTLEMENT_OPERATIONS = frozenset({
    "gateway_poll", "membership_admission_settlement", "account_purge", "encryption.key_job",
})
# Sweeps that only deliver, expire, retain or reconcile what already exists.
READ_ONLY_OPERATIONS = SETTLEMENT_OPERATIONS | frozenset({
    "auto_stop", "canonical_retention", "event_approval_digest", "event_asset_work",
    "event_certificate_resume", "event_judging_notices", "event_submission_integrity",
    "free_channel_drain", "github_contributions_refresh", "inventory_stock_snapshot",
    "issue_missing_bills", "kiosk_replay_cleanup", "loan_pickup_expiry", "loan_waitlist_lapse",
    "member_push_recovery", "membership_admission_expiry", "messaging_stop_consents",
    "notification_contract_outbox", "notification_escalation", "notification_legacy_inbound",
    "notification_media_cleanup", "notification_retention", "presence_expiry",
    "public_page_asset_cleanup", "rebuild_refund_cases", "report_rollup", "subject_export_recovery",
})


@contextmanager
def permitted(kinds):
    token = _permits.set(_permits.get() | frozenset(kinds))
    try:
        yield
    finally:
        _permits.reset(token)


@contextmanager
def enforcing_read_only():
    token = _enforce_read_only.set(True)
    try:
        yield
    finally:
        _enforce_read_only.reset(token)


def http_context(path, view_name):
    """The write context for one unsafe HTTP request (entered by the gate middleware)."""
    if path.startswith("/control/") or view_name in CONTROL_ROUTES or view_name in SETTLEMENT_ROUTES:
        return permitted(BOTH)
    if view_name in READ_ONLY_ROUTES:
        return nullcontext()
    return enforcing_read_only()


def fanout_context(operation):
    """The write context for one tenant of a scheduled sweep."""
    if operation in SETTLEMENT_OPERATIONS:
        return permitted(BOTH)
    if operation in READ_ONLY_OPERATIONS:
        return nullcontext()
    return enforcing_read_only()


def control_context():
    """Superadmin control services and the scheduled archive/purge run under this."""
    return permitted(BOTH)


def assert_space_writable(makerspace_id):
    permits = _permits.get()
    if BOTH <= permits:
        return
    from apps.makerspaces.models import Makerspace

    row = Makerspace.objects.filter(pk=makerspace_id).values_list(
        "lifecycle_state", "control_state__read_only_at",
    ).first()
    if row is None:
        return
    lifecycle_state, read_only_at = row
    from .errors import SpaceReadOnly, SpaceSuspended

    if lifecycle_state == Makerspace.LifecycleState.SUSPENDED and SUSPENDED not in permits:
        raise SpaceSuspended()
    if read_only_at is not None and _enforce_read_only.get() and READ_ONLY not in permits:
        raise SpaceReadOnly()
