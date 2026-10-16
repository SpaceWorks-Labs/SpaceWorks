"""Apply each authenticated batch item under the tenant gate and generation lock."""
import logging
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.makerspaces.platform import module_enabled
from apps.tenant_migration.gate_runtime import tenant_write
from .models_contract import NotificationDelivery
from .models_endpoints import ChannelConfiguration, NotificationEndpoint
from .notification_proofs import verified_callback
from .notification_delivery import MAX_ATTEMPTS, apply_callback
from .notification_providers import CallbackEvent
from .notification_wa_meta_callbacks import callback_event, destination, endpoint_for
from .notification_wa_meta_http import error_result
from .notification_wa_window import inbound_time

logger = logging.getLogger(__name__)


def apply_item(configuration, request, index, item):
    proxy = SimpleNamespace(body=request.body, headers=request.headers,
        meta_route_kwargs=request.parser_context["kwargs"], meta_item_index=index)
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        assert_mapped_write_allowed(configuration.makerspace_id)
        current = rbac.scope_notification_policy(ChannelConfiguration.objects.select_for_update(),
            makerspace_id=configuration.makerspace_id).get(pk=configuration.pk)
        if current.generation != configuration.generation or current.provider != "meta":
            return
        event = callback_event(current, proxy)
        if event is None:
            return
        if event.proof and not module_enabled(current.makerspace, "notifications"):
            return
        try:
            # Re-verifies the original signature through the registered factory.
            result = verified_callback(current, proxy)
        except ValidationError:
            # Expired, replayed, or sender-mismatched proof: acknowledge without PII.
            logger.info("notification.meta_proof_refused", extra={"configuration_id": current.pk})
            return
        kind, row = item
        if kind == "statuses" and event.state == "retrying":
            result = _retry_failure(current, row)
        if kind == "statuses" and result:
            _delivery_audit(current, row)
        if kind == "messages" and not event.opt_out:
            endpoint = result if event.proof else endpoint_for(current, destination(row.get("from")))
            moment = inbound_time(row.get("timestamp"))
            if endpoint and moment:
                rows = rbac.scope_notification_policy(NotificationEndpoint.objects.all(),
                    makerspace_id=current.makerspace_id).filter(pk=endpoint.pk,
                    configuration=current, integration_generation=current.generation,
                    integration_identity=current.integration_identity, revoked_at=None)
                changed = rows.filter(Q(last_inbound_at=None) | Q(last_inbound_at__lt=moment)).update(last_inbound_at=moment)
                if changed:
                    audit.record(None, "notification.whatsapp_inbound", makerspace=current.makerspace,
                        target=endpoint, meta={"channel": "whatsapp", "generation": current.generation})


def _delivery_rows(configuration, row):
    return rbac.scope_notification_policy(NotificationDelivery.objects.all(),
        makerspace_id=configuration.makerspace_id).filter(channel="whatsapp", provider="meta",
        integration_generation=configuration.generation, integration_identity=configuration.integration_identity,
        provider_id=row["id"])


def _retry_failure(configuration, row):
    """No premature email fallback on an authenticated transient failure callback."""
    changed = False
    for delivery in _delivery_rows(configuration, row).select_for_update():
        if delivery.state not in {"accepted", "sent"}:
            continue
        if delivery.attempt_count >= MAX_ATTEMPTS:
            changed = apply_callback(configuration, CallbackEvent(provider_id=row["id"], state="failed")) or changed
            continue
        error = row["errors"][0]
        delivery.state, delivery.retryable = "retrying", True
        delivery.last_error = error_result(400, {"error": error}).error_code
        delivery.next_attempt_at = timezone.now() + timedelta(seconds=min(30 * 2 ** delivery.attempt_count, 3600))
        delivery.claim_until = None
        delivery.save(update_fields=["state", "retryable", "last_error", "next_attempt_at", "claim_until", "updated_at"])
        changed = True
    return changed


def _delivery_audit(configuration, row):
    deliveries = _delivery_rows(configuration, row).filter(state__in=[row["status"], "retrying"])
    for delivery in deliveries:
        if row["status"] == "failed":
            errors = row.get("errors", [])
            error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
            # CallbackEvent has no error fields. Preserve only the fixed code
            # beside the state chosen by the shared layer or bounded retry helper.
            code = error_result(400, {"error": error}).error_code
            deliveries.filter(pk=delivery.pk).update(last_error=code, updated_at=timezone.now())
        audit.record(None, "notification.whatsapp_delivery_updated", makerspace=configuration.makerspace,
            target=delivery, meta={"channel": "whatsapp", "state": delivery.state,
                                   "generation": configuration.generation})
