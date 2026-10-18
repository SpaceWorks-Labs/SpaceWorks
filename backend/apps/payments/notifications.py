"""Stable notification import for the core ledger services."""
from .notifications_p2 import notify_payment

from .notification_projections import payment_subject

# MERGE-RECON(F): reuse payment_subject in the canonical renderer without a
# second legacy fan-out; staff projections must continue to omit payer amounts.
__all__ = ["notify_payment", "payment_subject"]
