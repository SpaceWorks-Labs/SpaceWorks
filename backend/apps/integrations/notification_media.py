"""A bearer is returned only to Twilio; storage and audits contain no bearer."""
from datetime import timedelta
from contextlib import ExitStack, contextmanager
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
from .notification_attachment_sources import (
    DocumentDeliveryError, attachment_references, authorized_attachment, render_attachment, source_for,
    attachment_tenant_ids,
)
from apps.tenant_migration.gate_errors import SourceMigrationGateError
from apps.tenant_migration.gate_runtime import boundary_tenant_write, fanout_tenant_write
from .models_contract import NotificationDelivery
from .models_notification_media import NotificationMediaGrant

logger = logging.getLogger(__name__)


@contextmanager
def _source_boundaries(tenant_ids):
    with ExitStack() as stack:
        for tenant_id in sorted(set(tenant_ids)):
            stack.enter_context(boundary_tenant_write(tenant_id))
        yield


def _discover(delivery):
    references = attachment_references(delivery.envelope)
    if len(references) != 1:
        raise DocumentDeliveryError("document_not_authorized")
    reference = references[0]
    return reference, attachment_tenant_ids(reference, makerspace_id=delivery.makerspace_id,
        recipient_id=delivery.envelope.recipient_id)


def digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def media_source_targets(token):
    """G's origin/source router calls this without consuming or authorizing a URL."""
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return set()
    targets = NotificationMediaGrant.objects.filter(token_digest=digest(token), consumed_at__isnull=True,
        expires_at__gt=timezone.now()).values_list("delivery__makerspace_id", "storage_makerspace_id").first()
    return {value for value in targets if value is not None} if targets else set()


def _matches(grant, reference):
    media_field = source_for(reference).media_field
    return (getattr(grant, media_field + "_id") == reference.document_id
            and grant.storage_makerspace_id is not None
            and grant.source_revision == reference.revision
            and grant.recipient_id_snapshot == grant.delivery.envelope.recipient_id
            and grant.integration_generation == grant.delivery.integration_generation
            and grant.integration_identity == grant.delivery.integration_identity)


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
    initial = rbac.scope_notification_policy(NotificationDelivery.objects.all(),
        makerspace_id=delivery.makerspace_id).get(pk=delivery.pk)
    reference, scopes = _discover(initial)
    with _source_boundaries(scopes), transaction.atomic():
        current = rbac.scope_notification_policy(NotificationDelivery.objects.all(),
            makerspace_id=delivery.makerspace_id).get(pk=delivery.pk)
        current_reference, current_scopes = _discover(current)
        if not live_delivery(current) or current_reference != reference or current_scopes != scopes:
            raise DocumentDeliveryError("document_not_authorized")
        config = current.endpoint.configuration
        base = validate_credentials(config.get_credentials()).public_base_url
        document = authorized_attachment(reference, makerspace_id=current.makerspace_id,
                                       recipient_id=current.envelope.recipient_id)
        token = secrets.token_urlsafe(32)
        media_field = source_for(reference).media_field
        grant = NotificationMediaGrant.objects.create(delivery=current,
            **{media_field + "_id": reference.document_id}, source_revision=reference.revision,
            storage_makerspace_id=getattr(document, "storage_makerspace_id", document.makerspace_id),
            recipient_id_snapshot=current.envelope.recipient_id,
            integration_generation=current.integration_generation, integration_identity=current.integration_identity,
            token_digest=digest(token), expires_at=timezone.now() + timedelta(minutes=10))
        audit.record(None, "notification.media_grant_issued", makerspace=current.makerspace,
            target=grant, meta={"delivery_id": current.pk,
                ("document_id" if media_field == "document" else "certificate_id"): reference.document_id})
    return base + reverse("notification-media", args=[token])


def consume_grant(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    seed = NotificationMediaGrant.objects.filter(token_digest=digest(token), consumed_at__isnull=True,
        expires_at__gt=timezone.now()).first()
    if seed is None:
        return None
    space_id = seed.delivery.makerspace_id
    try:
        expected_reference, scopes = _discover(seed.delivery)
        with _source_boundaries(scopes):
            return _consume_locked_sources(seed, expected_reference, scopes, space_id)
    except (SourceMigrationGateError, TenantNotRestored, DocumentDeliveryError):
        return None


def _consume_locked_sources(seed, expected_reference, scopes, space_id):
    with transaction.atomic():
        # Lock only the grant: the endpoint relation is nullable and must not
        # participate in a SELECT FOR UPDATE outer join.
        grant = rbac.scope_notification_policy(NotificationMediaGrant.objects.select_for_update(of=("self",)),
            makerspace_id=space_id, field="delivery__makerspace_id").filter(
                pk=seed.pk, consumed_at=None, expires_at__gt=timezone.now()).first()
        if grant is None or not live_delivery(grant.delivery):
            return None
        reference, current_scopes = _discover(grant.delivery)
        if reference != expected_reference or current_scopes != scopes:
            return None
        media_field = source_for(reference).media_field
        if not _matches(grant, reference):
            return None
        authorized_attachment(reference, makerspace_id=space_id,
                            recipient_id=grant.delivery.envelope.recipient_id)
        grant.consumed_at = timezone.now()
        grant.save(update_fields=["consumed_at"])
        audit.record(None, "notification.media_grant_consumed", makerspace=grant.delivery.makerspace,
            target=grant, meta={"delivery_id": grant.delivery_id,
                ("document_id" if media_field == "document" else "certificate_id"): reference.document_id})
    # A failed render must not roll back consumption and reopen the bearer.
    filename, pdf, _ = render_attachment(reference, makerspace_id=space_id,
        recipient_id=grant.delivery.envelope.recipient_id)
    # Storage reads run outside application row locks. A revoke/rotation can
    # commit during that read: consume stays committed, but bytes are dropped.
    final = rbac.scope_notification_policy(NotificationMediaGrant.objects.all(),
        makerspace_id=space_id, field="delivery__makerspace_id").filter(
            pk=seed.pk, consumed_at__isnull=False, expires_at__gt=timezone.now()).first()
    if final is None or not _matches(final, reference) or not live_delivery(final.delivery):
        return None
    if reference not in attachment_references(final.delivery.envelope):
        return None
    return filename, pdf

def cleanup_grants(limit=500):
    now = timezone.now()
    spent = Q(expires_at__lte=now) | Q(consumed_at__isnull=False)
    seeds = list(NotificationMediaGrant.objects.filter(spent).order_by("pk").values_list(
        "pk", "delivery__makerspace_id")[:limit])
    counts = {"deleted": 0, "skipped": 0, "failed": 0}
    for pk, space_id in seeds:
        try:
            with fanout_tenant_write(space_id, operation="notification_media_cleanup", counts=counts) as allowed:
                if not allowed:
                    continue
                with transaction.atomic():
                    rows = rbac.scope_notification_policy(NotificationMediaGrant.objects.select_for_update(of=("self",)),
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
    return counts
