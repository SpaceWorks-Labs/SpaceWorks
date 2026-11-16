"""Coalesced, durable Firebase inbox wake-ups; payloads contain no inbox data."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.integrations.firebase_web_config import effective
from apps.integrations.models_push import PlatformPushSettings
from apps.integrations.push_fcm import PushProviderError
from apps.integrations.push_firebase_browser import send_inbox_hint
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.operations.durable_dispatch import dispatch
from apps.space_controls.write_policy import fanout_context
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from apps.tenant_rls.context import tenant_context
from .access import personal_space
from .models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration

logger = logging.getLogger(__name__)
CLAIM_SECONDS = 120  # longer than the provider timeout, so a live send is never claimed twice


def mark_pending(inbox):
    """Called inside the new inbox row's transaction; persist bounded coalesced work."""
    if (not module_enabled(inbox.makerspace, "notifications")
            or not feature_enabled(inbox.makerspace, "notifications.web_push")
            or not PlatformPushSettings.objects.filter(pk=1).exclude(fcm_service_account="").exists()):
        return []
    config = PlatformPushSettings.objects.filter(pk=1).first()
    state = effective(config)
    if not state["configured"]:
        return []
    rows = BrowserFirebaseRegistration.objects.filter(
        makerspace_id=inbox.makerspace_id, user_id=inbox.user_id, project_id=state["config"]["project_id"], active=True, revoked_at__isnull=True)
    ids = list(rows.order_by("pk").values_list("pk", flat=True)[:10])
    if ids:
        rows.filter(pk__in=ids).update(wake_pending_seq=F("wake_pending_seq") + 1)
    return ids


def dispatch_pending(ids):
    # Even full-profile eager Celery runs in the request; only a resident broker may dispatch.
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return
    for pk in ids:
        try:
            dispatch(deliver_registration, pk)
        except Exception:
            logger.warning("browser_firebase_enqueue_failed")


def _pending():
    return BrowserFirebaseRegistration.objects.filter(
        active=True, revoked_at__isnull=True, wake_pending_seq__gt=F("wake_sent_seq")
    ).filter(Q(wake_retry_at__isnull=True) | Q(wake_retry_at__lte=timezone.now()))


@shared_task
def deliver_registration(pk):
    return _deliver(pk)


def _deliver(pk, *, context=None):
    row = BrowserFirebaseRegistration.objects.select_related("makerspace", "user").filter(pk=pk).first()
    config = PlatformPushSettings.objects.filter(pk=1).first()
    if not row or not config or not config.fcm_configured:
        return False

    state = effective(config)
    if not state["configured"] or state["config"]["project_id"] != row.project_id:
        return False

    try:
        # One registration, one tenant: the same boundary a sweep item takes, but a frozen
        # source simply leaves the wake-up pending for recovery (no fan-out loop here).
        with (fanout_context("browser_firebase_wakeup"), boundary_tenant_write(row.makerspace_id),
              tenant_context(row.makerspace_id, label="browser_firebase_wakeup")):
            claim = _claim(row, pk)
            if claim is None:
                return False
            epoch, target_seq = claim
            # No row lock is held across the provider call: the claim (wake_retry_at in the future) keeps other
            # workers off this registration, and the fence is re-checked when the result is recorded.
            if context:
                context.check()
            try:
                send_inbox_hint(config, row.project_id, row.get_fid(), epoch, context=context)
            except PushProviderError as exc:
                registrations = BrowserFirebaseRegistration.objects.filter(pk=pk, active=True)
                if exc.invalid_token:
                    registrations.update(active=False, revoked_at=timezone.now(), wake_retry_at=None)
                else:
                    registrations.update(wake_retry_at=timezone.now() + timedelta(seconds=60))
                return False
            if context:
                context.check()
            return _settle(row, pk, epoch, target_seq)
    except (PermissionDenied, Http404, SourceMigrationGateClosed):
        return False


def _claim(row, pk):
    """-> (owner_epoch, target_seq) once this worker owns the send, else None. Short transaction, owner row locked."""
    with transaction.atomic():
        owner = BrowserFirebaseInstallation.objects.select_for_update().filter(
            fid_hmac=row.fid_hmac, user_id=row.user_id).first()
        row.refresh_from_db()
        row.makerspace.refresh_from_db()
        if (not module_enabled(row.makerspace, "notifications")
                or not feature_enabled(row.makerspace, "notifications.web_push")):
            return None
        personal_space(row.user, row.makerspace_id)
        if not owner:
            return None
        if (not row.active or row.revoked_at or row.wake_pending_seq <= row.wake_sent_seq
                or (row.wake_retry_at and row.wake_retry_at > timezone.now())):
            return None
        # The lease: a worker that dies mid-send frees the registration again after CLAIM_SECONDS.
        BrowserFirebaseRegistration.objects.filter(pk=pk).update(
            wake_retry_at=timezone.now() + timedelta(seconds=CLAIM_SECONDS))
        # Do not lock registration over I/O: new inbox writes may increment it.
        return str(owner.owner_epoch), row.wake_pending_seq


def _settle(row, pk, epoch, target_seq):
    """Record a delivered hint, unless the installation changed hands during the send (then it stays pending)."""
    with transaction.atomic():
        owner = BrowserFirebaseInstallation.objects.select_for_update().filter(
            fid_hmac=row.fid_hmac, user_id=row.user_id).first()
        registrations = BrowserFirebaseRegistration.objects.filter(pk=pk, active=True)
        if owner is None or str(owner.owner_epoch) != epoch:
            registrations.update(wake_retry_at=None)
            return False
        registrations.update(wake_sent_seq=target_seq, wake_retry_at=None)
        return True


def sweep_pending(limit=100):
    """Recover pending work; cache cursor is a non-authoritative fairness hint."""
    count = 1 if settings.CELERY_TASK_ALWAYS_EAGER else limit
    key = "browser_firebase_wakeup_scan_cursor"
    try:
        cursor = int(cache.get(key, 0) or 0)
    except (ValueError, TypeError):
        cursor = 0
    except Exception:
        logger.warning("browser_firebase_cursor_read_failed")
        cursor = 0
    ids = list(_pending().filter(pk__gt=cursor).order_by("pk").values_list("pk", flat=True)[:count])
    if not ids and cursor:
        ids = list(_pending().order_by("pk").values_list("pk", flat=True)[:count])
    for pk in ids:
        try:
            # Advance even when the tenant is frozen or the owner is no longer eligible.
            try:
                cache.set(key, pk, timeout=86400)
            except Exception:
                logger.warning("browser_firebase_cursor_write_failed")
            if settings.CELERY_TASK_ALWAYS_EAGER:
                _deliver(pk)
            else:
                dispatch(deliver_registration, pk)
        except Exception:
            logger.warning("browser_firebase_recovery_failed")

def drain_chunk(context, cursor):
    """One provider attempt in a bounded free tick; scheduler owns the total deadline."""
    context.check()
    ids = list(_pending().filter(pk__gt=cursor).order_by("pk").values_list("pk", flat=True)[:2])
    if ids:
        _deliver(ids[0], context=context)
        context.check()
    return {"remaining": len(ids) > 1, "cursor": ids[0] if len(ids) > 1 else 0, "processed": int(bool(ids))}
