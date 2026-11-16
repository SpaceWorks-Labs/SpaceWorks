"""Stable notification import for the core ledger services."""
from .notifications_p2 import notify_payment

from .notification_projections import payment_subject

__all__ = ["notify_payment", "payment_subject"]
