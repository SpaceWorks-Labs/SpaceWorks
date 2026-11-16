"""config.push (versioned adapter config, acknowledged) and time.sync (signed server time), decision 321g.

Staff push a bounded JSON object; each push is a new immutable version. The adapter fetches the latest version and
acknowledges it (applied or rejected). Config is NOT a secret store: any key that looks like a credential is refused,
so a password or token is never kept in the database or shown in the console. Time is signed with the server's Ed25519 key.
"""
import json
import re

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.devices.adapter_access import adapter_device, authorize_staff, scoped_adapter
from apps.devices.adapters.caps.config_push import ACK
from apps.devices.models import AdapterConfigVersion
from apps.devices.services_adapter_core import (TIME_DOMAIN, TIME_NONCE, AdapterError, audit_adapter, check,
                                                current_kid as kid_now, framed, sign)
from apps.devices.services_adapter_hello import bump_config

MAX_BYTES = 16 * 1024
SECRETISH = re.compile(r"pass(word|wd)?|secret|token|api[_-]?key|private|credential", re.IGNORECASE)


def _screen(value, path="config"):
    if isinstance(value, dict):
        for key, item in value.items():
            if SECRETISH.search(str(key)):
                raise AdapterError("config_secret_refused", "Config keys must not name secrets; keep them on the adapter.",
                                   key=str(key)[:40])
            _screen(item, f"{path}.{key}")
    elif isinstance(value, list):
        for item in value:
            _screen(item, path)


def push(actor, device_id, config):
    """Staff: create the next version for an adapter and tell it a change is waiting (config_version + wake)."""
    device = scoped_adapter(actor, device_id, whole=True)
    if not isinstance(config, dict):
        raise AdapterError("invalid_payload", "The config must be a JSON object.")
    if len(json.dumps(config)) > MAX_BYTES:
        raise AdapterError("config_too_large", "The config is larger than 16 KiB.", status_code=413)
    _screen(config)
    with transaction.atomic():
        makerspace = device.makerspace
        last = AdapterConfigVersion.objects.select_for_update().filter(device=device).order_by("-version").first()
        row = AdapterConfigVersion.objects.create(makerspace=makerspace, device=device, config=config,
                                                  version=(last.version + 1) if last else 1, created_by=actor)
        audit.record(actor, "devices.adapter_config_pushed", makerspace=makerspace, target=device, meta={
            "device_id": str(device.pk), "version": row.version, "keys": len(config)})
        bump_config(device)
    return row


def history(actor, device_id):
    device = scoped_adapter(actor, device_id, whole=True)
    return AdapterConfigVersion.objects.filter(device=device)[:20]


def fetch(principal):
    """Adapter: the latest pushed version (or version 0 with an empty config)."""
    device = adapter_device(principal)
    row = AdapterConfigVersion.objects.filter(device=device).first()
    return {"version": row.version if row else 0, "config": row.config if row else {}}


def acknowledge(principal, body):
    check(ACK, body, label="config ack")
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        row = AdapterConfigVersion.objects.select_for_update().filter(device=device, version=body["version"]).first()
        if row is None:
            raise NotFound()
        if row.acked_at is None:
            row.ack_outcome, row.ack_detail, row.acked_at = body["outcome"], body.get("detail", ""), timezone.now()
            row.save(update_fields=["ack_outcome", "ack_detail", "acked_at"])
            audit_adapter(device.makerspace, device, "devices.adapter_config_acked", meta={
                "version": row.version, "outcome": row.ack_outcome})
    return {"version": row.version, "outcome": row.ack_outcome}


def server_time(principal, nonce):
    """A signed time: Ed25519 over ``framed(TIME_DOMAIN, nonce, kid, epoch)``.

    The adapter MUST choose a fresh nonce (16 to 64 of ``A-Z a-z 0-9 _ -``) so a reply cannot be replayed to it; the
    server never invents one (lead 10).
    """
    adapter_device(principal)
    if not TIME_NONCE.match(nonce or ""):
        raise AdapterError("invalid_nonce", "Send a fresh nonce of 16 to 64 letters, digits, '_' or '-'.")
    now = int(timezone.now().timestamp())
    kid, signature = sign(framed(TIME_DOMAIN, nonce, kid_now(), now))
    return {"server_time": now, "nonce": nonce, "kid": kid, "signature": signature}
