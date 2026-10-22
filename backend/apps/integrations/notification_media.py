"""A bearer is returned only to Twilio; storage and audits contain no bearer."""
from datetime import timedelta
import hashlib
import logging
import re
import secrets

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts import rbac
from apps.audit import services as audit
from apps.backup.not_restored import TenantNotRestored
from apps.payments.document_delivery import (
    DocumentDeliveryError, attachment_references, authorized_document, render_attachment,
)
from apps.tenant_migration.gate_errors import SourceMigrationGateError
from apps.tenant_migration.gate_runtime import fanout_tenant_write, tenant_write
from .models_contract import NotificationDelivery
from .models_notification_media import NotificationMediaGrant

logger = logging.getLogger(__name__)


def digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def live_delivery(delivery):
    from .notification_resolution import eligible, resolve, target_eligible
    if (delivery.channel != "whatsapp" or delivery.provider != "twilio" or not delivery.endpoint_id
            or delivery.state not in {"retrying", "accepted", "sent", "delivered", "read"}
            or delivery.makerspace_id != delivery.envelope.makerspace_id
            or not eligible(delivery.envelope)):
        return False
    if not target_eligible(delivery.envelope, delivery.channel, delivery.endpoint):
        return False
    endpoint = delivery.endpoint
    return bool(delivery.integration_generation == endpoint.integration_generation
                and delivery.integration_identity == endpoint.integration_identity
                and any(target.channel == delivery.channel and target.endpoint.pk == endpoint.pk
                        for target in resolve(delivery.envelope)))


def issue_grant(delivery):
    from .notification_wa_twilio_config import validate_credentials
    if not delivery.endpoint_id or delivery.channel != "whatsapp" or delivery.provider != "twilio":
        raise DocumentDeliveryError("document_not_authorized")
    with tenant_write(delivery.makerspace_id):
        current = rbac.scope_notification_policy(NotificationDelivery.objects.all(),
            makerspace_id=delivery.makerspace_id).get(pk=delivery.pk)
        references = attachment_references(current.envelope)
        if not live_delivery(current) or len(references) != 1:
            raise DocumentDeliveryError("document_not_authorized")
        config = current.endpoint.configuration
        base = validate_credentials(config.get_credentials()).public_base_url
        document = authorized_document(references[0], makerspace_id=current.makerspace_id,
                                       recipient_id=current.envelope.recipient_id)
        token = secrets.token_urlsafe(32)
        grant = NotificationMediaGrant.objects.create(delivery=current, document=document,
            token_digest=digest(token), expires_at=timezone.now() + timedelta(minutes=10))
        audit.record(None, "notification.media_grant_issued", makerspace=current.makerspace,
            target=grant, meta={"delivery_id": current.pk, "document_id": document.pk})
    return base + reverse("notification-media", args=[token])


def consume_grant(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    seed = NotificationMediaGrant.objects.filter(token_digest=digest(token)).values(
        "delivery__makerspace_id", "pk").first()
    if seed is None:
        return None
    space_id = seed["delivery__makerspace_id"]
    try:
        with tenant_write(space_id), transaction.atomic():
            # Lock only the grant: the endpoint relation is nullable and must not
            # participate in a SELECT FOR UPDATE outer join.
            grant = rbac.scope_notification_policy(NotificationMediaGrant.objects.select_for_update(),
                makerspace_id=space_id, field="delivery__makerspace_id").filter(
                    pk=seed["pk"], consumed_at=None, expires_at__gt=timezone.now()).first()
            if grant is None or not live_delivery(grant.delivery):
                return None
            reference = {"document_id": grant.document_id, "kind": grant.document.kind}
            if reference not in attachment_references(grant.delivery.envelope):
                return None
            authorized_document(reference, makerspace_id=space_id,
                                recipient_id=grant.delivery.envelope.recipient_id)
            grant.consumed_at = timezone.now()
            grant.save(update_fields=["consumed_at"])
            audit.record(None, "notification.media_grant_consumed", makerspace=grant.delivery.makerspace,
                target=grant, meta={"delivery_id": grant.delivery_id, "document_id": grant.document_id})
        # A failed render must not roll back consumption and reopen the bearer.
        filename, pdf, _ = render_attachment(reference, makerspace_id=space_id,
            recipient_id=grant.delivery.envelope.recipient_id)
        return filename, pdf
    except (SourceMigrationGateError, TenantNotRestored, DocumentDeliveryError):
        return None


def cleanup_grants(limit=500, *, after_id=0):
    now = timezone.now()
    spent = Q(expires_at__lte=now) | Q(consumed_at__isnull=False)
    seeds = list(NotificationMediaGrant.objects.filter(spent, pk__gt=after_id).order_by("pk").values_list(
        "pk", "delivery__makerspace_id")[:limit])
    counts = {"deleted": 0, "skipped": 0, "failed": 0}
    for pk, space_id in seeds:
        from apps.operations.cloud_jobs.bounded import check
        check()
        try:
            with fanout_tenant_write(space_id, operation="notification_media_cleanup", counts=counts) as allowed:
                if not allowed:
                    continue
                with transaction.atomic():
                    rows = rbac.scope_notification_policy(NotificationMediaGrant.objects.select_for_update(),
                        makerspace_id=space_id, field="delivery__makerspace_id").filter(pk=pk).filter(spent)
                    grant = rows.first()
                    if grant is not None:
                        grant.delete()
                        from apps.makerspaces.models import Makerspace
                        audit.record(None, "notification.media_grant_cleaned", makerspace=Makerspace.objects.get(pk=space_id),
                                     meta={"grant_id": pk})
                counts["deleted"] += int(grant is not None)
        except (SourceMigrationGateError, TenantNotRestored):
            counts["skipped"] += 1
            continue
        except Exception as exc:
            counts["failed"] += 1
            logger.warning("notification_media_cleanup_failed", extra={
                "grant_id": pk, "failure_type": type(exc).__name__,
            })
    from .mail_providers.budget_config import free_profile
    if free_profile():
        return {**counts, "cursor": seeds[-1][0] if seeds else 0, "remaining": len(seeds) == limit}
    return counts
