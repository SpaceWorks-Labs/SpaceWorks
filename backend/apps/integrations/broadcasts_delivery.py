"""Live checks run inside dispatch_delivery, including release and every retry."""

from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace
from .broadcasts_registry import ADAPTERS
from .delivery_content import render

ATTEMPTS_PER_RETRY = 4
RETRY_START = "broadcast_retry_start"


def attempt_limit(log):
    return log.source_metadata.get(RETRY_START, 0) + ATTEMPTS_PER_RETRY


def prepare(log):
    adapter = ADAPTERS.get(log.source_kind)
    if adapter is None:
        return False
    delivery = adapter.delivery_model.objects.select_related("campaign").filter(
        pk=log.source_id, outbox_id=log.pk, recipient_id=log.recipient_id,
        campaign__makerspace_id=log.makerspace_id,
    ).first()
    if not delivery:
        return False
    campaign = delivery.campaign
    if campaign.status not in {"queued", "sending"}:
        return False
    try:
        adapter.authorize(campaign, campaign.created_by)
    except APIException:
        return False
    if not adapter.eligible(campaign, delivery.recipient):
        return False
    values = adapter.render(campaign, delivery.recipient)
    if values is None:
        return False
    render(log, subject=values["subject"], text_body=values["text_body"],
           html_body=values.get("html_body", ""), to_email=values.get("to_email", delivery.recipient.email))
    return True


def retry(log, actor):
    from .broadcasts_worker import transition
    adapter = ADAPTERS[log.source_kind]
    rows = adapter.delivery_model.objects.filter(
        pk=log.source_id, outbox_id=log.pk, recipient_id=log.recipient_id,
        campaign__makerspace_id=log.makerspace_id,
    )
    campaign_id = rows.values_list("campaign_id", flat=True).first()
    if campaign_id is None:
        raise ValidationError(gettext("This broadcast delivery no longer exists."))
    # Match reconciliation's tenant-before-campaign order: audit FKs also lock
    # the tenant, so holding the campaign while waiting for it can deadlock.
    makerspace = Makerspace.objects.select_for_update().get(pk=log.makerspace_id)
    campaign = adapter.campaign_model.objects.select_for_update().get(pk=campaign_id)
    campaign.makerspace = makerspace
    delivery = rows.select_for_update().first()
    if (campaign.status not in {"queued", "sending", "failed"} or delivery is None
            or delivery.status not in {"pending", "failed"}):
        raise ValidationError(gettext("This broadcast delivery cannot be retried."))
    # Do not authorize using the retrying operator: prepare() still rechecks the
    # original sender and recipient before every SMTP attempt, including release.
    if campaign.status == "failed":
        campaign.completed_at = None
        transition(adapter, campaign, "sending")
    delivery.status = "pending"
    delivery.save(update_fields=["status", "updated_at"])
    # Keep lifetime attempts for history; renew only this manual retry's budget.
    # The caller holds the outbox lock and rolls this back with domain state.
    log.source_metadata = {**log.source_metadata, RETRY_START: log.attempts}
    log.save(update_fields=["source_metadata", "updated_at"])
    record(actor, f"{adapter.audit_prefix}.delivery_requeued", makerspace=campaign.makerspace, target=delivery)


def finished(log):
    adapter = ADAPTERS.get(log.source_kind)
    if adapter is None:
        return
    with transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        from apps.tenant_migration.gate_runtime import _boundary_shared_locks, assert_write_allowed
        # Delivery/recovery already holds the dedicated source-gate boundary.
        # Reacquiring here can deadlock behind a migration waiting on that boundary.
        if log.makerspace_id not in _boundary_shared_locks.get():
            assert_write_allowed(log.makerspace_id)
        assert_mapped_write_allowed(log.makerspace_id)
        # Match manual retry: outbox -> tenant -> campaign -> delivery. Recovery
        # and SMTP callbacks may hold snapshots from before a retry committed.
        log = EmailLog.objects.select_for_update().filter(
            pk=log.pk, makerspace_id=log.makerspace_id, source_kind=log.source_kind,
        ).first()
        if log is None or log.status not in {"sent", "skipped", "failed"}:
            return
        rows = adapter.delivery_model.objects.filter(pk=log.source_id, outbox_id=log.pk)
        campaign_id = rows.values_list("campaign_id", flat=True).first()
        if campaign_id is None:
            return
        makerspace = Makerspace.objects.select_for_update().get(pk=log.makerspace_id)
        campaign = adapter.campaign_model.objects.select_for_update().get(pk=campaign_id)
        campaign.makerspace = makerspace
        delivery = rows.select_for_update().first()
        status = "pending" if log.status == "failed" and log.attempts < attempt_limit(log) else log.status
        if delivery is None or delivery.status == status:
            return
        delivery.status = status
        delivery.save(update_fields=["status", "updated_at"])
        record(None, f"{adapter.audit_prefix}.delivery_{log.status}",
               makerspace=campaign.makerspace, target=delivery)
    from .broadcasts_worker import reconcile
    reconcile(log.source_kind, campaign.pk)
