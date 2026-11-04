"""Bounded retention for canonical addressed legs and processed ingress receipts.

Never selected: in-flight, held or retryable legs; legs of unprocessed envelopes; legs
or receipts a pending correlation barrier, durable replay, media grant or unverified
legacy mapping still needs. Frozen legacy tables, suppressions, aliases, consent and
provider references are never touched here.
"""
import logging
from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from .models_contract import NotificationDelivery
from .models_cutover import NotificationIngress, NotificationLegacyMapping, NotificationProviderReference
from .models_messaging_consent import MessagingRecipientCorrelation
from .models_notification_media import NotificationMediaGrant
from .notification_cutover import boundary, state as cutover_state

logger = logging.getLogger(__name__)
SUCCESS_DAYS = 90
FAILED_DAYS = 365
RECEIPT_DAYS = 30
BATCH_SIZE = 1000
TERMINAL = ("accepted", "sent", "delivered", "read", "skipped", "failed")
PUSH_ACTIVE = ("pending", "sending", "held")


def _push_children():
    # The optional inbox app owns per-device children. Tombstoning keeps it installed
    # (rows/migrations stay); were it ever uninstalled, its table could still reference
    # parents, so push legs are then left untouched.
    if not apps.is_installed("apps.notifications"):
        return None
    return apps.get_model("notifications", "MemberPushDelivery").objects.filter(envelope_delivery=OuterRef("pk"))


def expired_deliveries(queryset, now, *, mappings_verified):
    children = _push_children()
    channels = ("sms", "whatsapp", "native_push") if children is not None else ("sms", "whatsapp")
    rows = queryset.filter(channel__in=channels, state__in=TERMINAL, retryable=False,
        claim_until__isnull=True, envelope__processed_at__isnull=False)
    # Derived status: delivery/read evidence wins over a later failure observation.
    failed = Q(state="failed", delivered_at__isnull=True, read_at__isnull=True)
    if children is not None:
        rows = rows.alias(child_failed=Exists(children.filter(status="failed")),
            child_active=Exists(children.filter(status__in=PUSH_ACTIVE))).exclude(child_active=True)
        failed |= Q(channel="native_push", child_failed=True)
    rows = rows.filter(Q(created_at__lt=now - timedelta(days=FAILED_DAYS))
        | (Q(created_at__lt=now - timedelta(days=SUCCESS_DAYS)) & ~failed))
    receipts = NotificationIngress.objects.filter(channel=OuterRef("channel"),
        sender_key=OuterRef("sender_key")).exclude(state="processed")
    reference = NotificationProviderReference.objects.filter(provider=OuterRef("provider"),
        sender_key=OuterRef("sender_key"), provider_id=OuterRef("provider_id"),
        delivery_reference=OuterRef("pk"), ambiguous=False)
    rows = rows.alias(
        pending_receipt=Exists(receipts),
        probing=Exists(MessagingRecipientCorrelation.objects.filter(
            probe_notification_delivery=OuterRef("pk"), state="probing")),
        granted=Exists(NotificationMediaGrant.objects.filter(delivery=OuterRef("pk"))),
        referenced=Exists(reference),
    ).exclude(pending_receipt=True).exclude(probing=True).exclude(granted=True).exclude(
        # Late callbacks settle a deleted leg only through its exact permanent reference.
        Q(channel__in=("sms", "whatsapp")) & ~Q(provider_id="") & Q(referenced=False))
    if not mappings_verified:
        rows = rows.exclude(pk__in=NotificationLegacyMapping.objects.filter(
            canonical_model="NotificationDelivery").values("canonical_id"))
    return rows


def expired_receipts(now, *, mappings_verified):
    rows = NotificationIngress.objects.filter(state="processed", protection_applied=True,
        processed_at__lt=now - timedelta(days=RECEIPT_DAYS))
    if not mappings_verified:
        rows = rows.exclude(pk__in=NotificationLegacyMapping.objects.filter(
            canonical_model="NotificationIngress").values("canonical_id"))
    return rows


def _delete_batch(queryset, limit):
    # Lock only the selected rows so a concurrent claim/callback keeps its row.
    with transaction.atomic():
        ids = list(queryset.select_for_update(skip_locked=True, of=("self",))
                   .order_by("pk").values_list("pk", flat=True)[:limit])
        queryset.model.objects.filter(pk__in=ids).delete()
        return len(ids)


def run_canonical_retention(*, now=None, limit=BATCH_SIZE):
    if type(limit) is not int or limit < 1:
        raise ValueError("Canonical retention batch size must be a positive integer.")
    now = now or timezone.now()
    counts = {"deleted": 0, "receipts": 0, "skipped": 0, "failed": 0}
    # Shared cutover lock first: conversion, replay and verification checkpoints exclude us.
    with boundary():
        verified = cutover_state().reconciled_at is not None
        tenants = rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk")
        for space in tenants.iterator():
            try:
                with fanout_tenant_write(space.pk, operation="canonical_retention", counts=counts) as permitted:
                    if not permitted:
                        continue
                    eligible = expired_deliveries(rbac.scope_for_scheduled_work(
                        NotificationDelivery.objects.all(), makerspace_id=space.pk), now,
                        mappings_verified=verified)
                    counts["deleted"] += _delete_batch(eligible, limit)
            except Exception as exc:
                counts["failed"] += 1
                logger.error("canonical_retention_failed", extra={
                    "makerspace_id": space.pk, "failure_type": type(exc).__name__})
        # Receipts are deployment-local replay state, kept across tenant purge/freeze.
        try:
            counts["receipts"] += _delete_batch(expired_receipts(now, mappings_verified=verified), limit)
        except Exception as exc:
            counts["failed"] += 1
            logger.error("canonical_receipt_retention_failed", extra={"failure_type": type(exc).__name__})
    logger.info("canonical_retention_completed", extra=counts)
    return counts
