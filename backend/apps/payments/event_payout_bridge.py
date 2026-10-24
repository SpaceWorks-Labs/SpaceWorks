"""Lane G installation of the core payout ledger's ports. Query-free; runs in ready().

- Scan policy: the existing shared upload-scanner settings (EVENT_ASSET_SCAN_BACKEND,
  EVENT_ASSET_CLAMAV_HOST/PORT); there is no finance-specific scanner switch.
- Preflight facts and retained cancellation coordination: the reimbursement add-on's
  readers. Its models stay installed when the add-on or Events is tombstoned, so retained
  obligations keep resolving; core itself never imports a removable workflow.
"""
from django.conf import settings


def shared_scan_policy():
    from .event_payouts.scan_policy import ScannerPolicy
    backend = settings.EVENT_ASSET_SCAN_BACKEND
    return ScannerPolicy(backend=backend, host=settings.EVENT_ASSET_CLAMAV_HOST or None,
                         port=settings.EVENT_ASSET_CLAMAV_PORT)


def install():
    from .event_payouts import coordination, preflight, scan_policy
    from apps.event_reimbursements.cancellation_coordination import RetainedCancellationProvider
    from apps.event_reimbursements.payout_facts import ReimbursementPayoutFacts
    scan_policy.install(shared_scan_policy)
    preflight.install(ReimbursementPayoutFacts)
    coordination.install(RetainedCancellationProvider)
    from apps.integrations.notification_sources import register_source
    from .event_payouts.notices import NOTICE_SOURCE
    # Core personal payout notices stay deliverable when Events or the add-on is removed.
    register_source("finance.event_payout", NOTICE_SOURCE)
