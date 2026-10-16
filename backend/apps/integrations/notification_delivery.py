"""Claims are short transactions. Network I/O runs after their locks are released."""
from datetime import timedelta
from random import randint

from django.db import transaction
from django.utils import timezone

from .models_contract import NotificationDelivery as Delivery
from .notification_providers import ProviderResult, provider_for, safe_error
from .notification_resolution import eligible, resolve, target_eligible

MAX_ATTEMPTS = 4
SUCCESS = {"accepted", "sent", "delivered", "read"}
RANK = {"retrying": 0, "accepted": 1, "sent": 2, "failed": 3, "skipped": 3, "delivered": 4, "read": 5}


def apply_callback(configuration, event):
    """Only call with an event returned by this integration's verify_callback."""
    if event.state not in RANK or not event.provider_id:
        return False
    with transaction.atomic():
        rows = Delivery.objects.select_for_update().filter(
            makerspace=configuration.makerspace, channel=configuration.channel,
            provider=configuration.provider, integration_generation=configuration.generation,
            integration_identity=configuration.integration_identity,
        )
        rows = rows.filter(pk=event.delivery_id) if event.delivery_id else rows.filter(provider_id=event.provider_id)
        changed = False
        for row in rows:
            if row.provider_id and row.provider_id != event.provider_id:
                continue
            # A read/delivered acknowledgement cannot be undone by a late failure.
            if event.state == "failed" and row.state in {"accepted", "sent"}:
                row.state, row.retryable = "failed", False
            elif RANK[event.state] > RANK[row.state] and event.state in SUCCESS:
                row.state, row.retryable = event.state, False
            else:
                continue
            row.next_attempt_at = None
            row.claim_until = None
            row.provider_id = event.provider_id
            row.save(update_fields=["state", "provider_id", "retryable", "next_attempt_at", "claim_until", "updated_at"])
            changed = True
    if changed and event.state == "failed":
        for row in rows:
            fallback_if_exhausted(row.envelope)
        from .notification_outbox import enqueue
        for row in rows:
            transaction.on_commit(lambda pk=row.envelope_id: enqueue(pk), robust=True)
    return changed


def ensure_deliveries(envelope, *, fallback=False):
    targets = resolve(envelope, fallback=fallback)
    for target in targets:
        if fallback and target.channel != "email":
            continue
        if envelope.deliveries.filter(channel=target.channel).exists():
            # Reconnecting installs a NEW personal identity. An old private intent
            # must never silently acquire that endpoint on a retry or release.
            continue
        endpoint = target.endpoint
        Delivery.objects.get_or_create(envelope=envelope, channel=target.channel, defaults={
                "target_key": f"endpoint:{endpoint.pk}" if endpoint else target.channel,
                "makerspace": envelope.makerspace, "endpoint": endpoint,
                "provider": endpoint.provider if endpoint else "builtin",
                "integration_generation": endpoint.integration_generation if endpoint else 0,
                "integration_identity": endpoint.integration_identity if endpoint else "",
            })
    return envelope.deliveries.all()


def claim(delivery_id):
    now = timezone.now()
    with transaction.atomic():
        row = Delivery.objects.select_for_update().get(pk=delivery_id)
        if row.state in SUCCESS | {"skipped"}:
            return None
        if row.state == "failed" and not row.retryable:
            return None
        if row.claim_until and row.claim_until > now:
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
        row.save(update_fields=["claim_until", "attempt_count", "ambiguous_count", "updated_at"])
    return row


def send(delivery_id):
    row = claim(delivery_id)
    if row is None:
        return
    envelope = row.envelope
    # Resolve again: preference withdrawal and integration rotation invalidate a queue.
    other = envelope.deliveries.exclude(channel="email")
    fallback = (other.exists() and not other.filter(state__in=SUCCESS).exists()
                and not other.filter(state="retrying").exists())
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
        if row.channel == "whatsapp":
            from .notification_resolution import whatsapp_template
            template = whatsapp_template(row)
            from .notification_wa_window import in_session_window
            in_window = in_session_window(row.endpoint)
            if not in_window and template is None:
                return record_result(row, ProviderResult(False, error_code="template_required"))
            rendered["whatsapp_template"] = ({"name": template.template_name, "variables": template.variables,
                                               "locale": template.locale} if template else None)
        from .notification_builtin import send_builtin
        from .notification_quotas import reserve
        if not reserve(row):
            result = ProviderResult(False, error_code="quota_exceeded")
        elif row.endpoint_id:
            provider = provider_for(row.endpoint.configuration)
            result = provider.send(row, rendered) if provider else ProviderResult(False, error_code="not_configured")
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
        # A callback can win the race with the send response.
        if current.state in SUCCESS or (current.state == "failed" and not current.retryable):
            return current
        current.claim_until = None
        current.provider_id = result.provider_id or current.provider_id
        current.ambiguous_count += int(result.ambiguous)
        retry = result.retryable and current.attempt_count < MAX_ATTEMPTS and current.ambiguous_count < 2
        current.state = ("sent" if current.provider == "builtin" else "accepted") if result.accepted else "retrying" if retry else "failed"
        current.retryable = bool(retry and not result.accepted)
        current.last_error = "" if result.accepted else safe_error(result)
        delay = min(max(result.retry_after or 0, 30 * 2 ** current.attempt_count + randint(0, 30)), 3600)
        current.next_attempt_at = timezone.now() + timedelta(seconds=delay) if current.retryable else None
        current.save()
    if current.state == "failed":
        fallback_if_exhausted(current.envelope)
    return current


def fallback_if_exhausted(envelope):
    rows = envelope.deliveries.exclude(channel="email")
    if not rows.filter(state__in=SUCCESS).exists() and not rows.filter(state="retrying").exists():
        ensure_deliveries(envelope, fallback=True)
