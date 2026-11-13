"""Wallet device registrations (Apple's pass web service): every change is audited.

A device registering for a pass's updates, changing its push token or unregistering is a state change
on a tenant row, so it is written under the tenant write gate and leaves an audit entry. The actor is
None (Apple's servers, not an account); the audit names the pass and platform only, never the device
identifier or the push token.
"""
from apps.audit import services as audit

from ..models import WalletDeviceRegistration
from .credentials import digest

PUSH_TOKEN_MAX = 200


def _record(row, action, **meta):
    audit.record(None, action, makerspace=row.makerspace, target=row,
                 meta={"pass_id": row.pk, "platform": row.platform, **meta})


def register_device(row, device, push_token):
    """Register (or refresh the push token of) ``device`` for ``row``. Returns True when newly created."""
    from apps.tenant_migration.gate_runtime import tenant_write
    push = str(push_token or "")[:PUSH_TOKEN_MAX]
    with tenant_write(row.makerspace_id):
        existing = WalletDeviceRegistration.objects.select_for_update().filter(
            wallet_pass=row, device_digest=digest(device)).first()
        if existing is None:
            WalletDeviceRegistration.objects.create(wallet_pass=row, device_digest=digest(device), push_token=push)
            _record(row, "wallet_pass.device_registered", created=True)
            return True
        if existing.push_token != push:
            existing.push_token = push
            existing.save(update_fields=["push_token"])
            _record(row, "wallet_pass.device_registered", created=False)
        return False


def unregister_device(row, device):
    """Stop updates for ``device`` on ``row``; audited only when a registration was removed."""
    from apps.tenant_migration.gate_runtime import tenant_write
    with tenant_write(row.makerspace_id):
        deleted, _ = WalletDeviceRegistration.objects.filter(wallet_pass=row, device_digest=digest(device)).delete()
        if deleted:
            _record(row, "wallet_pass.device_unregistered")
    return bool(deleted)
