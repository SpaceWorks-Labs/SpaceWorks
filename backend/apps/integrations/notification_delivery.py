"""Claims are short transactions. Network I/O runs after their locks are released."""
from datetime import timedelta
from random import randint

from django.db import transaction
from django.utils import timezone

from .models_contract import NotificationDelivery as Delivery
from .notification_providers import ProviderResult, provider_for, safe_error
from .notification_resolution import eligible, resolve, target_eligible
from .notification_cutover import guarded, state as cutover_state

MAX_ATTEMPTS = 4
SUCCESS = {"accepted", "sent", "delivered", "read"}
RANK = {"held": 0, "retrying": 0, "accepted": 1, "sent": 2, "failed": 3, "skipped": 3, "delivered": 4, "read": 5}


@guarded()
def ensure_deliveries(envelope, *, fallback=False):
    if cutover_state().route != "canonical":
        return envelope.deliveries.all()
    from apps.tenant_migration.gate_runtime import tenant_write
    with tenant_write(envelope.makerspace_id):
        return _ensure_deliveries(envelope, fallback=fallback)


def _ensure_deliveries(envelope, *, fallback=False):
    if envelope.source_kind == "migration.history":
        return envelope.deliveries.all()
    targets = resolve(envelope, fallback=fallback)
    for target in targets:
        if fallback and target.channel != "email":
            continue
        if envelope.deliveries.filter(channel=target.channel).exists():
            # Reconnecting installs a NEW personal identity. An old private intent
            # must never silently acquire that endpoint on a retry or release.
            continue
        endpoint = target.endpoint
        config = endpoint.configuration if endpoint else None
        sender = None
        if target.channel == "sms":
            from .models_endpoints import ChannelConfiguration
            from .notification_sender import sms_sender
            config = ChannelConfiguration.objects.get(makerspace=envelope.makerspace, channel="sms")
            sender = sms_sender(config)
        from .notification_sender import configuration_sender_key
        from .messaging.protections import recipient_hash
        Delivery.objects.get_or_create(envelope=envelope, channel=target.channel, defaults={
                "target_key": f"endpoint:{endpoint.pk}" if endpoint else target.channel,
                "makerspace": envelope.makerspace, "endpoint": endpoint,
                "provider": config.provider if config else "builtin",
                "integration_generation": config.generation if config else 0,
                "integration_identity": config.integration_identity if config else "",
                "sender_key": sender.sender_key if sender else configuration_sender_key(config) if config and target.channel == "whatsapp" else "",
                "provider_source": sender.provider_source if sender else "own" if config else "",
                "credential_version": config.credential_version if config else 0,
                "recipient_phone_hash": recipient_hash("phone", envelope.recipient.phone_e164 if target.channel == "sms" else endpoint.destination)
                    if target.channel in {"sms", "whatsapp"} else "",
            })
    return envelope.deliveries.all()


@guarded(sending=True)
def claim(delivery_id):
    now = timezone.now()
    with transaction.atomic():
        row = Delivery.objects.select_for_update().get(pk=delivery_id)
        if row.historical or row.state in SUCCESS | {"skipped", "held"}:
            return None
        if row.state == "failed" and not row.retryable:
            return None
        if row.claim_until and row.claim_until > now:
            return None
        if row.claim_until and row.claim_until <= now and row.channel in {"sms", "whatsapp"}:
            row.state, row.retryable, row.last_error = "held", False, "unknown_provider_outcome"
            row.save(update_fields=["state", "retryable", "last_error", "updated_at"])
            return None
        if row.attempt_count >= MAX_ATTEMPTS:
            row.state, row.retryable, row.claim_until, row.next_attempt_at = "failed", False, None, None
            row.last_error = "attempt_budget_exhausted"
            row.save()
            return None
        if row.claim_until and row.claim_until <= now:
            row.ambiguous_count += 1
            if row.ambiguous_count >= 2:
                row.state, row.retryable, row.claim_until, row.next_attempt_at = "failed", False, None, None
                row.last_error = "timeout"
                row.save()
                return None
        if row.next_attempt_at and row.next_attempt_at > now:
            return None
        row.claim_until = now + timedelta(minutes=5)
        row.attempt_count += 1
        if row.provider == "meta":
            # The next signed attempt has its own provider message. Old callbacks
            # cannot bind to it by ID or by their previous attempt reference.
            row.provider_id = ""
        row.save(update_fields=["claim_until", "provider_id", "attempt_count", "ambiguous_count", "updated_at"])
    return row


@guarded(sending=True)
def send(delivery_id):
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    tenant_id = Delivery.objects.filter(pk=delivery_id).values_list("makerspace_id", flat=True).first()
    if tenant_id is None:
        return
    with boundary_tenant_write(tenant_id):
        return _send(delivery_id)


def _send(delivery_id):
    row = claim(delivery_id)
    if row is None:
        return
    envelope = row.envelope
    # Resolve again: preference withdrawal and integration rotation invalidate a queue.
    other = envelope.deliveries.exclude(channel="email")
    fallback = (other.exists() and not other.filter(state__in=SUCCESS).exists()
                and not other.filter(state__in=["retrying", "held"]).exists())
    targets = resolve(envelope, fallback=fallback)
    selected = any(t.channel == row.channel and getattr(t.endpoint, "pk", None) == row.endpoint_id for t in targets)
    if not selected or not eligible(envelope) or not target_eligible(envelope, row.channel, row.endpoint):
        finish_skipped(row.pk, "live_eligibility_changed")
        return
    if row.endpoint_id and (row.integration_generation != row.endpoint.integration_generation
                           or row.integration_identity != row.endpoint.integration_identity):
        finish_skipped(row.pk, "integration_changed")
        return
    try:
        from .notification_sources import render
        rendered = render(envelope)
        if row.channel not in {"in_app", "native_push"}:
            from .notification_links import external_links
            rendered = external_links(envelope.makerspace, rendered)
        if row.channel == "whatsapp":
            from .notification_addressed import prepare_whatsapp
            if not prepare_whatsapp(row):
                return
            from .notification_resolution import whatsapp_template
            template = whatsapp_template(row)
            from .notification_wa_window import in_session_window
            in_window = in_session_window(row.endpoint)
            if not in_window and template is None and envelope.source_kind != "payments.document":
                return record_result(row, ProviderResult(False, error_code="template_required"))
            rendered["whatsapp_template"] = ({"name": template.template_name, "variables": template.variables,
                                               "locale": template.locale} if template else None)
        from .notification_builtin import send_builtin
        from .notification_quotas import reserve
        if not reserve(row):
            result = ProviderResult(False, error_code="quota_exceeded")
        elif row.channel == "sms":
            from .notification_addressed import send_sms
            result = send_sms(row)
        elif row.endpoint_id:
            provider = provider_for(row.endpoint.configuration)
            if provider:
                from .notification_document_dispatch import send_document
                result = send_document(provider, row, rendered)
            else:
                result = ProviderResult(False, error_code="not_configured")
        else:
            result = send_builtin(row, rendered)
    except TimeoutError:
        result = ProviderResult(False, retryable=True, error_code="timeout", ambiguous=True)
    except Exception as exc:
        ambiguous = type(exc).__name__ in {"Timeout", "ReadTimeout", "ConnectTimeout", "ReadTimeoutError"}
        result = ProviderResult(False, retryable=True, error_code="timeout" if ambiguous else "provider_error", ambiguous=ambiguous)
    return record_result(row, result)


def finish_skipped(pk, reason):
    Delivery.objects.filter(pk=pk).exclude(state__in=SUCCESS).update(
        state="skipped", last_error=reason, retryable=False, claim_until=None, next_attempt_at=None,
        updated_at=timezone.now(),
    )


def record_result(row, result):
    if result.error_code == "skipped":
        finish_skipped(row.pk, "transport_suppressed")
        return Delivery.objects.get(pk=row.pk)
    with transaction.atomic():
        current = Delivery.objects.select_for_update().get(pk=row.pk)
        if current.attempt_count != row.attempt_count:
            return current
        # A callback can win the race with the send response.
        if current.state in SUCCESS or (current.state == "failed" and not current.retryable):
            return current
        if current.provider == "meta" and current.provider_id and current.claim_until is None:
            # A transient callback already scheduled this attempt's retry.
            return current
        current.claim_until = None
        current.provider_id = result.provider_id or current.provider_id
        current.ambiguous_count += int(result.ambiguous)
        addressed_hold = result.ambiguous and current.channel in {"sms", "whatsapp"}
        retry = result.retryable and not addressed_hold and current.attempt_count < MAX_ATTEMPTS and current.ambiguous_count < 2
        current.state = ("sent" if current.provider == "builtin" else "accepted") if result.accepted else "retrying" if retry else "failed"
        current.retryable = bool(retry and not result.accepted)
        if addressed_hold and not result.accepted:
            current.state = "held"
        current.last_error = "" if result.accepted else safe_error(result)
        if result.accepted:
            current.accepted_at = current.accepted_at or timezone.now()
            if current.state == "sent":
                current.sent_at = current.sent_at or current.accepted_at
        elif current.state == "failed":
            current.failed_at = current.failed_at or timezone.now()
        delay = min(max(result.retry_after or 0, 30 * 2 ** current.attempt_count + randint(0, 30)), 3600)
        current.next_attempt_at = timezone.now() + timedelta(seconds=delay) if current.retryable else None
        current.save()
        from .notification_provider_references import remember
        remember(current)
    if current.channel == "whatsapp" and not (result.accepted or result.ambiguous or current.provider_id):
        from .messaging.correlation import release_canonical_probe
        release_canonical_probe(current)
    if current.state == "failed":
        fallback_if_exhausted(current.envelope)
    return current


def fallback_if_exhausted(envelope):
    if envelope.source_kind == "migration.history":
        return
    rows = envelope.deliveries.exclude(channel="email")
    if not rows.filter(state__in=SUCCESS).exists() and not rows.filter(state__in=["retrying", "held"]).exists():
        ensure_deliveries(envelope, fallback=True)


# Explicit compatibility barrel; callback fact processing has no send authority.
from .notification_callbacks import apply_callback  # noqa: E402,F401
