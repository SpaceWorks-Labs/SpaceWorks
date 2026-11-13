"""Commands the server sends an adapter (control, indicate, aim, snapshot, unlock): enqueue, lease, ack.

Staff enqueue through ``enqueue`` (RBAC, machine scope, schema-validated params, audit with the staff actor).
The adapter leases one command at a time (at-least-once, lease expiry returns it to the queue, bounded
attempts) and acknowledges it with an outcome. A command outlives neither its TTL nor its device key: an
expired command is never leased again, a lease never runs past the command's TTL, and an ack that arrives after
the lease lapsed, after the TTL or under a rotated key is refused (and recorded) instead of completing it.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.devices import protocol
from apps.devices.adapter_access import adapter_device, adapters_enabled, scoped_binding, switch_for
from apps.devices.adapters.registry import command_schema
from apps.devices.adapters.schema import CODE, obj, text
from apps.devices.models import AdapterCommand, Device
from apps.devices.services_adapter_core import AdapterError, audit_adapter, check
from apps.devices.services_locks import lock_tenant

COMMAND_TTL_SECONDS = 600
ACK = obj({"lease_token": text(128, minLength=32), "outcome": {"type": "string", "enum": ["succeeded", "failed"]},
           "result_code": CODE}, ["lease_token", "outcome"])
Status = AdapterCommand.Status


def enqueue(actor, binding_id, capability, command, params):
    # Resolved through the actor's MANAGE_DEVICES scope, so another tenant's binding UUID is the same 404 as a
    # missing one, never a 403 that confirms it exists (L-A6). Machine scope and the switch are checked inside.
    binding = scoped_binding(actor, binding_id, child=switch_for(capability))
    schema = command_schema(capability, command)
    if schema is None:
        raise AdapterError("command_unknown", "No such command for this capability.")
    check(schema, params, label="command params")
    if capability not in binding.capabilities or not binding.enabled:
        raise AdapterError("capability_missing", "This binding does not serve that capability.", status_code=409)
    with transaction.atomic():
        makerspace = lock_tenant(binding.makerspace_id)
        device = Device.objects.select_for_update().get(pk=binding.device_id)
        if device.status != Device.Status.ACTIVE:
            raise AdapterError("adapter_unavailable", "The adapter is not active.", status_code=409)
        now = timezone.now()
        row = AdapterCommand.objects.create(
            makerspace=makerspace, device=device, binding=binding, device_key_version=device.key_version,
            capability=capability, command=command, params=params, created_by=actor,
            expires_at=now + timedelta(seconds=COMMAND_TTL_SECONDS))
        # Params are never echoed (a pose is staff-only data); the command name and ids are the trail.
        audit.record(actor, "devices.adapter_command_queued", makerspace=makerspace, target=device, meta={
            "device_id": str(device.pk), "binding_id": str(binding.pk), "capability": capability,
            "command": command, "command_id": str(row.pk)})
        from apps.devices.services_adapter_webhook import wake
        wake(device, "command.queued", binding_id=binding.pk, capability=capability, command=command)
    return row


def _release_expired(device, now):
    """Expire every command past its TTL (queued OR leased) first, then requeue only lapsed leases still in TTL.

    The order matters: requeueing first would hand a door ``unlock`` the adapter sat on past its TTL straight
    back out as a fresh lease.
    """
    AdapterCommand.objects.filter(device=device, status__in=(Status.QUEUED, Status.LEASED), expires_at__lte=now).update(
        status=Status.EXPIRED, result_code="expired", completed_at=now, lease_token_digest=None, lease_expires_at=None)
    AdapterCommand.objects.filter(device=device, status=Status.LEASED, lease_expires_at__lte=now,
                                  expires_at__gt=now).update(
        status=Status.QUEUED, lease_token_digest=None, lease_expires_at=None)


def _next_queued(device, now):
    return AdapterCommand.objects.select_for_update(skip_locked=True, of=("self",)).select_related("binding").filter(
        device=device, status=Status.QUEUED, device_key_version=device.key_version, binding__enabled=True,
        expires_at__gt=now,
    ).order_by("created_at", "id").first()


def _undeliverable(device, command):
    """Why a queued command must not reach the adapter, or "" to deliver it.

    A command whose capability's child switch went off after it was queued (a door ``unlock`` once
    ``machines.integrations.access`` is off, a ``snapshot`` once ``.video`` is off) fails closed instead of running.
    """
    if command.attempts >= settings.DEVICE_COMMAND_MAX_ATTEMPTS:
        return "attempts_exhausted"
    switch = switch_for(command.capability)
    if switch and not adapters_enabled(device.makerspace_id, switch):
        return "capability_switched_off"
    return ""


def lease(principal):
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        _release_expired(device, now)
        command = _next_queued(device, now)
        while command is not None and (refusal := _undeliverable(device, command)):
            command.status, command.result_code, command.completed_at = Status.FAILED, refusal, now
            command.save(update_fields=["status", "result_code", "completed_at"])
            command = _next_queued(device, now)
        if command is None:
            return {"command": None}
        token = secrets.token_urlsafe(32)
        command.status, command.attempts = Status.LEASED, command.attempts + 1
        command.lease_token_digest = protocol.sha256_hex(token.encode("ascii"))
        # A lease never outlives the command: the adapter may not act on it after its TTL.
        command.lease_expires_at = min(now + timedelta(seconds=settings.DEVICE_COMMAND_LEASE_SECONDS),
                                       command.expires_at)
        command.save(update_fields=["status", "attempts", "lease_token_digest", "lease_expires_at"])
        # The queue row names who asked (``queued``); this row is the delivery half of the trail. Neither the lease
        # token nor the params (a pose is staff-only data) are recorded.
        audit_adapter(device.makerspace, device, "devices.adapter_command_leased", meta={
            "binding_id": str(command.binding_id), "command_id": str(command.pk),
            "capability": command.capability, "command": command.command, "attempt": command.attempts})
    return {"command": {
        "command_id": str(command.pk), "binding_id": str(command.binding_id), "capability": command.capability,
        "command": command.command, "params": command.params, "lease_token": token,
        "lease_expires_at": int(command.lease_expires_at.timestamp())}}


def _late(command, device, now):
    """Why an ack holding the right token is still refused, or "": key rotated, command expired, lease lapsed."""
    if command.device_key_version != device.key_version:
        return "key_rotated"
    if command.expires_at <= now:
        return "command_expired"
    if command.lease_expires_at is None or command.lease_expires_at <= now:
        return "lease_lapsed"
    return ""


def _refuse_late(device, command, reason, outcome, now):
    """Close (expired, key rotated) or requeue (lapsed lease, still in TTL) a late-acked command, with a trail."""
    command.lease_token_digest, command.lease_expires_at = None, None
    if reason == "lease_lapsed":
        command.status = Status.QUEUED
    else:
        command.status, command.result_code, command.completed_at = Status.EXPIRED, reason, now
    command.save(update_fields=["status", "result_code", "completed_at", "lease_token_digest", "lease_expires_at"])
    audit_adapter(device.makerspace, device, "devices.adapter_command_ack_refused", meta={
        "binding_id": str(command.binding_id), "command_id": str(command.pk), "reason": reason,
        "reported_outcome": outcome})


def acknowledge(principal, command_id, body):
    check(ACK, body, label="command ack")
    now = timezone.now()
    late = ""
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        command = AdapterCommand.objects.select_for_update().filter(pk=command_id, device=device).first()
        if command is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        digest = protocol.sha256_hex(body["lease_token"].encode("utf-8"))
        if command.lease_token_digest is None and command.status in (Status.SUCCEEDED, Status.FAILED):
            return {"command_id": str(command.pk), "status": command.status}  # idempotent re-ack
        if command.lease_token_digest is None or not secrets.compare_digest(command.lease_token_digest, digest):
            raise AdapterError("lease_mismatch", "That lease token does not own this command.", status_code=409)
        if command.status != Status.LEASED:
            raise AdapterError("lease_expired", "The lease is no longer active.", status_code=410)
        late = _late(command, device, now)
        if late:
            # Persisted before the error is raised (outside this block), so the refusal and its trail commit.
            _refuse_late(device, command, late, body["outcome"], now)
        else:
            command.status = Status.SUCCEEDED if body["outcome"] == "succeeded" else Status.FAILED
            command.result_code = body.get("result_code", "")
            command.completed_at, command.lease_token_digest = now, None
            command.save(update_fields=["status", "result_code", "completed_at", "lease_token_digest"])
            audit_adapter(device.makerspace, device, "devices.adapter_command_acked", meta={
                "binding_id": str(command.binding_id), "command_id": str(command.pk),
                "capability": command.capability, "command": command.command, "outcome": command.status})
    if late == "key_rotated":
        raise AdapterError("lease_mismatch", "That lease belongs to a retired device key.", status_code=409)
    if late:
        raise AdapterError("lease_expired", "The lease is no longer active.", status_code=410)
    return {"command_id": str(command.pk), "status": command.status}
