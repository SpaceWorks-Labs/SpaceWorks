"""Retention for the unusual-login check (``login_security_contract.RETENTION``; #157).

- ``KnownNetwork``: deleted 90 days after it was last seen;
- ``KnownDevice``: deleted 180 days after its last completed sign-in (revoked ones too);
- ``SecurityAlert``: labels cleared once the link expires, the row deleted 30 days later;
- ``WebAuthnCeremony``: deleted one day after it expired.

Each model is purged on its own so one failure never stops the others; bounded by the
cloud-jobs chunk on the free profile. Runs inside ``purge_spent_challenges``.
"""

import logging

from django.utils import timezone

from apps.accounts.login_security_contract import RETENTION
from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)


def _cutoff(label, now):
    return now - RETENTION[label][1]


def purge_login_risk_state(now=None):
    from apps.accounts.models import KnownDevice, KnownNetwork, SecurityAlert, WebAuthnCeremony
    now = now or timezone.now()
    deleted = {}
    targets = (
        (KnownNetwork, lambda: KnownNetwork.objects.filter(last_seen__lt=_cutoff("accounts.KnownNetwork", now))),
        (KnownDevice, lambda: KnownDevice.objects.filter(last_verified_at__lt=_cutoff("accounts.KnownDevice", now))),
        (SecurityAlert, lambda: SecurityAlert.objects.filter(expires_at__lt=_cutoff("accounts.SecurityAlert#row", now))),
        (WebAuthnCeremony, lambda: WebAuthnCeremony.objects.filter(
            expires_at__lt=_cutoff("accounts.WebAuthnCeremony", now))),
    )
    for model, rows in targets:
        label = model._meta.label
        try:
            deleted[label], _ = bounded.delete(rows(), label)
        except Exception:
            logger.exception("login_risk_purge_failed", extra={"model": label})
            deleted[label] = 0
    try:
        deleted["accounts.SecurityAlert#labels"] = SecurityAlert.objects.filter(
            expires_at__lte=now).exclude(network_label__isnull=True, ua_label__isnull=True).update(
            network_label=None, ua_label=None)
    except Exception:
        logger.exception("login_risk_purge_failed", extra={"model": "accounts.SecurityAlert#labels"})
        deleted["accounts.SecurityAlert#labels"] = 0
    return deleted
