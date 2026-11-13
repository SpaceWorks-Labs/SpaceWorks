"""Atomic lease claims and token-fenced writes around provider I/O."""
from django.utils.translation import gettext
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone

from apps.integrations.models import MessagingDelivery
from apps.tenant_migration.gate_runtime import boundary_tenant_write, tenant_write
from .correlation import claim_probe, release_probe
from .eligibility import eligibility
from .locks import lock_whatsapp_sender
from .outcomes import derived_status, observe, save_outcome
from .protections import recipient_hash, suppressed
from .resolver import resolve_sender
from .projections import PROJECTION_KEYS, render_sms
from .segments import prepare_sms
from .templates import binding_for
from .transport import send_message


def due_filter(now):
    return Q(status="pending", next_attempt_at__lte=now) | Q(status="sending", lease_until__lt=now)


def claim(pk):
    now, token = timezone.now(), uuid4()
    changed = MessagingDelivery.objects.filter(pk=pk).filter(due_filter(now), attempts__lt=F("max_attempts")).update(
        status="sending", lease_token=token, lease_until=now + timedelta(seconds=90), attempts=F("attempts") + 1)
    return token if changed else None


def _skip(row, reason):
    row.status = "suppressed" if reason == "suppressed" else "skipped"
    row.skip_reason = "" if reason == "suppressed" else reason
    row.lease_token = row.lease_until = None
    save_outcome(row)


def _prepare(pk):
    snapshot = MessagingDelivery.objects.select_related("makerspace").filter(pk=pk).first()
    if snapshot is None:
        return None
    sender = resolve_sender(snapshot.makerspace, snapshot.channel)
    # Lock order: tenant gate -> WhatsApp sender -> delivery -> correlation.
    with tenant_write(snapshot.makerspace_id):
        if snapshot.channel == "whatsapp":
            lock_whatsapp_sender(sender.sender_key if sender else snapshot.sender_key)
        previous = MessagingDelivery.objects.select_for_update().filter(pk=pk).values_list("status", flat=True).first()
        reclaimed = previous == "sending"
        token = claim(pk)
        if token is None:
            return None
        row = MessagingDelivery.objects.select_related("makerspace", "user").get(pk=pk)
        reason = eligibility(row)
        if reason != "ok":
            _skip(row, reason)
            return None
        current = resolve_sender(row.makerspace, row.channel)
        if sender is None or current is None or sender != current:
            # Restart under the new sender lock rather than acquiring locks out of order.
            row.status, row.next_attempt_at = "pending", timezone.now() + timedelta(seconds=5)
            row.attempts -= 1
            row.lease_token = row.lease_until = None
            save_outcome(row)
            return None
        row.sender_key, row.provider, row.provider_source = sender.sender_key, sender.provider, sender.provider_source
        row.recipient_phone_hash = recipient_hash("phone", row.user.phone_e164)
        kwargs = {"to": row.user.phone_e164, "delivery_id": row.pk}
        try:
            allowed = PROJECTION_KEYS[(row.feature, row.event, row.audience)]
            if row.context.keys() - set(allowed):
                raise ValidationError(gettext("Unreviewed template context"))
            if row.channel == "sms":
                sms = prepare_sms("SpaceWorks messaging test. Your sender is working." if row.source_type == "messaging_test"
                                  else render_sms(row.feature, row.event, row.audience, row.context))
                row.estimated_segments = row.segments = sms.estimated_segments
                kwargs["body"] = sms.body
            else:
                binding = binding_for(row.makerspace, sender, row.feature, row.event, row.audience)
                if binding is None or any(key not in allowed for key in binding.parameters):
                    raise ValidationError(gettext("Template unavailable"))
                row.template_name = binding.template_name
                kwargs.update(template_name=binding.template_name, language=binding.language,
                              parameters=[str(row.context.get(key) or "") for key in binding.parameters])
        except (ValidationError, KeyError):
            row.status, row.error_code, row.failed_at = "failed", "template_rejected", timezone.now()
            row.lease_token = row.lease_until = None
            save_outcome(row)
            return None
        # Re-read sender protections immediately before each provider submission.
        if suppressed(row.channel, row.sender_key, row.recipient_phone_hash):
            _skip(row, "suppressed")
            return None
        probe = False
        if row.channel == "whatsapp":
            barrier = claim_probe(row, row.recipient_phone_hash, reclaimed=reclaimed)
            probe = barrier == "probe"
            if barrier in {"blocked", "expired"}:
                _skip(row, "identity_unconfirmed")
                return None
            if barrier == "wait":
                row.status, row.next_attempt_at = "pending", timezone.now() + timedelta(minutes=5)
                row.attempts -= 1
                row.lease_token = row.lease_until = None
                save_outcome(row)
                return None
            if barrier == "ambiguous":
                row.status, row.error_code, row.failed_at = "failed", "ambiguous_timeout", timezone.now()
                row.lease_token = row.lease_until = None
                save_outcome(row)
                return None
        save_outcome(row, "messaging.delivery_claimed")
        return row.pk, token, sender, kwargs, probe


def complete(pk, token, sender, result, *, probe=False):
    snapshot = MessagingDelivery.objects.filter(pk=pk, lease_token=token).first()
    if snapshot is None:
        return False
    # Same order as preparation; an enclosing boundary supplies the gate lock.
    with tenant_write(snapshot.makerspace_id):
        if sender.channel == "whatsapp":
            lock_whatsapp_sender(sender.sender_key)
        row = MessagingDelivery.objects.select_for_update().filter(pk=pk, lease_token=token).first()
        if row is None:
            return False
        now = timezone.now()
        if result.message_id:
            row.provider_message_id = result.message_id
            observe(row, "accepted", at=now)
        elif row.provider_message_id:
            pass  # A verified early callback already proved the provider outcome.
        elif probe and result.ambiguous:
            row.status, row.error_code, row.failed_at = "failed", "ambiguous_timeout", now
        elif result.retryable and row.attempts < row.max_attempts:
            # A webhook may have proved acceptance while the HTTP response was lost.
            if row.progress_rank == 0:
                row.status = "pending"
                row.next_attempt_at = now + timedelta(seconds=min(60 * 2 ** (row.attempts - 1), 3600))
            row.error_code = result.error_code
        else:
            code = result.error_code
            if sender.provider == "meta" and (code.startswith("132") or code in {"131026", "131047"}):
                code = "template_rejected"
            if result.retryable and row.attempts >= row.max_attempts:
                code = "attempts_exhausted"
            observe(row, "failed", at=now, error_code=code)
        if result.error_code in {"21610", "21211", "21614"}:
            from .stops import suppress_recipient
            suppress_recipient(row.channel, row.sender_key, row.recipient_phone_hash,
                reason="provider_opt_out" if result.error_code == "21610" else "permanent_failure")
        if probe and not (result.message_id or row.provider_message_id or row.progress_rank or result.ambiguous):
            # Definitive non-acceptance permits a fresh probe after repair.
            release_probe(row)
        row.status = derived_status(row)
        row.lease_token = row.lease_until = None
        save_outcome(row)
        return True


def deliver(pk):
    """Stale Celery messages are inert after reconciliation code is deployed."""
    return None
