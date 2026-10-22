"""Keep legacy EmailLog retries attached to the personal envelope's live authority."""
from .models_contract import NotificationDelivery


def prepare(log):
    from .notification_delivery import SUCCESS
    from .notification_resolution import eligible, resolve
    from .notification_sources import render
    from .delivery_content import render as render_email
    from .mail_providers.budget_config import free_profile
    states = ["retrying"]
    if free_profile() and log.email_retryable and log.error == "email_operator_reconciled":
        states.append("failed")
    row = NotificationDelivery.objects.filter(pk=log.source_metadata.get("delivery_id"),
        envelope_id=log.source_id, makerspace_id=log.makerspace_id,
        envelope__recipient_id=log.recipient_id, channel="email", state__in=states).first()
    if row is None or not eligible(row.envelope):
        return False
    others = row.envelope.deliveries.exclude(channel="email")
    fallback = (others.exists() and not others.filter(state__in=SUCCESS).exists()
                and not others.filter(state="retrying").exists())
    if not any(target.channel == "email" for target in resolve(row.envelope, fallback=fallback)):
        return False
    from apps.hardware_requests.notifications_p2_email import render_email as equipment_email
    content = equipment_email(row.envelope, render(row.envelope))
    from .notification_links import external_links
    content = external_links(row.envelope.makerspace, content)
    render_email(log, to_email=row.envelope.recipient.email, subject=content.get("subject", "Space Works"),
                 text_body=content.get("text", ""), html_body=content.get("html", ""),
                 attachments=_attachments(row.envelope))
    return True


def retry(log, actor):
    from rest_framework.exceptions import ValidationError
    raise ValidationError({"delivery": "Personal deliveries use the envelope retry budget."})


def register_email_source():
    from .delivery_sources import DeliverySource, register
    register("notification.envelope", DeliverySource(prepare, finished=finished, digestible=False, retry=retry))
    from .notification_direct_mail import KIND, prepare as prepare_direct
    register(KIND, DeliverySource(prepare_direct, digestible=False))
    from apps.payments.document_delivery import prepare_document_email
    register("payments.document", DeliverySource(prepare_document_email, digestible=False))


def _attachments(envelope):
    from apps.payments.document_delivery import attachment_references
    return attachment_references(envelope)


def finished(log):
    from .mail_providers.budget_config import free_profile
    if not free_profile() or log.status != "sent":
        return
    from django.db import transaction
    from contextlib import nullcontext
    from apps.audit import services as audit
    from apps.operations.cloud_jobs.bounded import check
    from apps.tenant_migration.gate_runtime import (
        _boundary_shared_locks, assert_write_allowed, boundary_tenant_write,
    )
    from apps.encryption.write_fence import assert_mapped_write_allowed
    if log.makerspace_id is None:
        return
    check()
    # Reuse the retained source boundary during ordinary drains. Acquiring a
    # second shared lock behind a queued migration writer can deadlock that pin.
    boundary = (nullcontext() if log.makerspace_id in _boundary_shared_locks.get()
                else boundary_tenant_write(log.makerspace_id))
    with boundary:
        assert_write_allowed(log.makerspace_id)
        with transaction.atomic():
            check()
            assert_mapped_write_allowed(log.makerspace_id)
            _finish_locked(log, audit, check)


def _finish_locked(log, audit, check):
    row = NotificationDelivery.objects.select_for_update().filter(pk=log.source_metadata.get("delivery_id"),
        envelope_id=log.source_id, makerspace_id=log.makerspace_id,
        envelope__recipient_id=log.recipient_id, channel="email").first()
    if row is None or row.state not in {"retrying", "failed"}:
        return
    check()
    row.state, row.retryable, row.claim_until, row.next_attempt_at = "sent", False, None, None
    row.provider_id, row.last_error = f"email:{log.pk}", ""
    row.save(update_fields=["state", "retryable", "claim_until", "next_attempt_at", "provider_id", "last_error", "updated_at"])
    audit.record(None, "notification.email_accepted", makerspace=log.makerspace, target=row,
                 meta={"delivery_id": row.pk, "email_log_id": log.pk})
